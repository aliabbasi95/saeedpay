# apps/wallets/services/payment/payment_processing_service.py

import logging

from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from apps.wallets.models import Payment, PaymentRequest, Wallet
from apps.wallets.services.payment.payment_authorization_service import (
    authorize_cash_payment,
    authorize_credit_payment,
)
from apps.wallets.services.payment.payment_request_service import (
    check_and_expire_payment_request,
    ensure_no_active_payment_exists,
    ensure_request_can_be_paid,
    resolve_payment_method,
    validate_payment_request_payer_access,
    validate_wallet_ownership,
)
from apps.wallets.services.payment.payment_rollback_service import (
    rollback_cash_payment,
    rollback_credit_payment,
)
from apps.wallets.services.payment.payment_settlement_service import (
    settle_cash_payment,
    settle_credit_payment,
)
from apps.wallets.services.payment.payment_shared import (
    create_event,
    ensure_payment_request_status,
    get_latest_payment_for_request,
    merchant_confirm_expiry,
)
from apps.wallets.utils.choices import (
    PaymentEventType,
    PaymentFlowType,
    PaymentMethod,
    PaymentRequestStatus,
    PaymentStatus,
)
from saeedpay.logging import log_event

logger = logging.getLogger("saeedpay.wallets.payment")


def _create_payment_safely(
    *,
    payment_request: PaymentRequest,
    payer,
    payer_wallet: Wallet,
    amount,
    method,
    flow_type,
):
    try:
        return Payment.objects.create(
            payment_request=payment_request,
            payer=payer,
            payer_wallet=payer_wallet,
            amount=amount,
            method=method,
            flow_type=flow_type,
            status=PaymentStatus.CREATED,
        )
    except IntegrityError as exc:
        if "uniq_active_payment_per_request" in str(exc):
            log_event(
                logger,
                level="warning",
                event="payment_create_integrity_conflict",
                message="Duplicate active payment prevented by DB constraint.",
                module="wallets.payment",
                action="_create_payment_safely",
                payment_request_id=payment_request.id,
                payment_request_reference=payment_request.reference_code,
                user_id=getattr(payer, "id", None),
                store_id=payment_request.store_id,
                amount=amount,
                flow_type=flow_type,
            )
            raise ValidationError(
                "این درخواست پرداخت در حال پردازش است.",
                code="payment_in_progress",
            ) from exc
        raise


def _mark_payment_awaiting_merchant(payment: Payment):
    payment.merchant_confirm_expires_at = merchant_confirm_expiry()
    payment.mark_awaiting_merchant()


def _move_request_to_awaiting_merchant(
    *,
    payment_request: PaymentRequest,
    user,
    wallet,
    merchant_deadline,
    payment: Payment,
):
    from_status = payment_request.status

    payment_request.mark_awaiting_merchant(
        user=user,
        wallet=wallet,
        merchant_deadline=merchant_deadline,
    )

    create_event(
        payment_request=payment_request,
        payment=payment,
        actor=user,
        event_type=PaymentEventType.AWAITING_MERCHANT,
        from_status=from_status,
        to_status=payment_request.status,
        description="Payment request is waiting for merchant confirmation.",
        extra_data={
            "merchant_confirm_expires_at": (
                merchant_deadline.isoformat() if merchant_deadline else None
            ),
            "wallet_id": wallet.id if wallet else None,
        },
    )

    log_event(
        logger,
        level="info",
        event="payment_awaiting_merchant_confirmation",
        message="Payment request moved to awaiting merchant confirmation.",
        module="wallets.payment",
        action="_move_request_to_awaiting_merchant",
        payment_request_id=payment_request.id,
        payment_request_reference=payment_request.reference_code,
        payment_id=payment.id,
        payment_reference=payment.reference_code,
        user_id=getattr(user, "id", None),
        store_id=payment_request.store_id,
        from_status=from_status,
        to_status=payment_request.status,
        merchant_confirm_expires_at=merchant_deadline,
    )


def _log_request_completed_event(
    *,
    payment_request: PaymentRequest,
    user,
    wallet,
    payment: Payment,
    from_status,
):
    create_event(
        payment_request=payment_request,
        payment=payment,
        actor=user,
        event_type=PaymentEventType.PAYMENT_COMPLETED,
        from_status=from_status,
        to_status=payment_request.status,
        description="Payment request completed.",
        extra_data={
            "wallet_id": wallet.id if wallet else None,
        },
    )

    log_event(
        logger,
        level="info",
        event="payment_request_completed",
        message="Payment request completed.",
        module="wallets.payment",
        action="_log_request_completed_event",
        payment_request_id=payment_request.id,
        payment_request_reference=payment_request.reference_code,
        payment_id=payment.id,
        payment_reference=payment.reference_code,
        user_id=getattr(user, "id", None),
        store_id=payment_request.store_id,
        from_status=from_status,
        to_status=payment_request.status,
    )


def _complete_qr_payment(
    *,
    payment_request: PaymentRequest,
    payment: Payment,
    user,
    wallet,
):
    if payment.method == PaymentMethod.CASH:
        settle_cash_payment(payment)
    elif payment.method == PaymentMethod.CREDIT:
        settle_credit_payment(payment)
    else:
        raise ValidationError(
            "روش پرداخت پشتیبانی نمی‌شود.",
            code="unsupported_payment_method",
        )

    payment.mark_completed()
    payment_request.mark_completed_direct(
        user=user,
        wallet=wallet,
    )
    _log_request_completed_event(
        payment_request=payment_request,
        user=user,
        wallet=wallet,
        payment=payment,
        from_status=PaymentRequestStatus.CREATED,
    )


def _move_online_payment_forward(
    *,
    payment_request: PaymentRequest,
    payment: Payment,
    user,
    wallet,
):
    _mark_payment_awaiting_merchant(payment)
    _move_request_to_awaiting_merchant(
        payment_request=payment_request,
        user=user,
        wallet=wallet,
        merchant_deadline=payment.merchant_confirm_expires_at,
        payment=payment,
    )


def pay_payment_request(request_obj: PaymentRequest, user, wallet: Wallet):
    with transaction.atomic():
        payment_request = PaymentRequest.objects.select_for_update().get(
            pk=request_obj.pk
        )

        log_event(
            logger,
            level="info",
            event="payment_processing_started",
            message="Payment processing started.",
            module="wallets.payment",
            action="pay_payment_request",
            payment_request_id=payment_request.id,
            payment_request_reference=payment_request.reference_code,
            store_id=payment_request.store_id,
            user_id=getattr(user, "id", None),
            amount=payment_request.amount,
            flow_type=payment_request.flow_type,
            status=payment_request.status,
        )

        check_and_expire_payment_request(payment_request)
        validate_payment_request_payer_access(
            payment_request=payment_request,
            user=user,
        )
        ensure_no_active_payment_exists(payment_request)
        ensure_request_can_be_paid(payment_request)

        customer_wallet = validate_wallet_ownership(user=user, wallet=wallet)
        payment_method = resolve_payment_method(customer_wallet)

        payment = _create_payment_safely(
            payment_request=payment_request,
            payer=user,
            payer_wallet=customer_wallet,
            amount=payment_request.amount,
            method=payment_method,
            flow_type=payment_request.flow_type,
        )

        log_event(
            logger,
            level="info",
            event="payment_created",
            message="Payment object created.",
            module="wallets.payment",
            action="pay_payment_request",
            payment_request_id=payment_request.id,
            payment_request_reference=payment_request.reference_code,
            payment_id=payment.id,
            payment_reference=payment.reference_code,
            store_id=payment_request.store_id,
            user_id=getattr(user, "id", None),
            amount=payment.amount,
            flow_type=payment.flow_type,
            payment_method=payment.method,
            payment_status=payment.status,
        )

        if payment.method == PaymentMethod.CASH:
            authorize_cash_payment(payment, customer_wallet)
        elif payment.method == PaymentMethod.CREDIT:
            authorize_credit_payment(payment)
        else:
            raise ValidationError(
                "روش پرداخت پشتیبانی نمی‌شود.",
                code="unsupported_payment_method",
            )

        if payment.flow_type == PaymentFlowType.QR_POS:
            _complete_qr_payment(
                payment_request=payment_request,
                payment=payment,
                user=user,
                wallet=customer_wallet,
            )
        else:
            _move_online_payment_forward(
                payment_request=payment_request,
                payment=payment,
                user=user,
                wallet=customer_wallet,
            )

        log_event(
            logger,
            level="info",
            event="payment_processing_finished",
            message="Payment processing finished.",
            module="wallets.payment",
            action="pay_payment_request",
            payment_request_id=payment_request.id,
            payment_request_reference=payment_request.reference_code,
            payment_id=payment.id,
            payment_reference=payment.reference_code,
            store_id=payment_request.store_id,
            user_id=getattr(user, "id", None),
            amount=payment.amount,
            flow_type=payment.flow_type,
            payment_method=payment.method,
            payment_status=payment.status,
            payment_request_status=payment_request.status,
        )

        return payment


def verify_payment_request(payment_request: PaymentRequest, *, store=None) -> Payment:
    with transaction.atomic():
        request_obj = PaymentRequest.objects.select_for_update().get(
            pk=payment_request.pk
        )

        if store is not None and request_obj.store_id != store.id:
            log_event(
                logger,
                level="warning",
                event="payment_verify_forbidden_store",
                message="Forbidden store attempted payment verification.",
                module="wallets.payment",
                action="verify_payment_request",
                payment_request_id=request_obj.id,
                payment_request_reference=request_obj.reference_code,
                store_id=getattr(store, "id", None),
                owner_store_id=request_obj.store_id,
            )
            raise ValidationError(
                "این درخواست پرداخت متعلق به این فروشگاه نیست.",
                code="forbidden_store",
            )

        if request_obj.flow_type != PaymentFlowType.ONLINE:
            raise ValidationError(
                "نهایی‌سازی برای این نوع درخواست پرداخت مجاز نیست.",
                code="unsupported_flow_type",
            )

        log_event(
            logger,
            level="info",
            event="payment_verification_started",
            message="Payment verification started.",
            module="wallets.payment",
            action="verify_payment_request",
            payment_request_id=request_obj.id,
            payment_request_reference=request_obj.reference_code,
            store_id=request_obj.store_id,
            flow_type=request_obj.flow_type,
            payment_request_status=request_obj.status,
        )

        check_and_expire_payment_request(request_obj)
        latest_payment = get_latest_payment_for_request(request_obj)

        if request_obj.status == PaymentRequestStatus.COMPLETED:
            raise ValidationError(
                "این درخواست پرداخت قبلاً نهایی شده است.",
                code="already_completed",
            )

        if request_obj.status == PaymentRequestStatus.CANCELLED:
            raise ValidationError(
                "درخواست پرداخت لغو شده است.",
                code="cancelled",
            )

        if request_obj.status == PaymentRequestStatus.EXPIRED:
            raise ValidationError(
                "درخواست پرداخت منقضی شده است.",
                code="expired",
            )

        ensure_payment_request_status(
            request_obj,
            allowed_statuses={PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION},
            error_message="پرداخت قابل نهایی‌سازی نیست یا قبلاً تایید شده است.",
            error_code="invalid_state",
        )

        payment = (
            Payment.objects.select_for_update()
            .filter(
                payment_request=request_obj,
                status=PaymentStatus.AWAITING_MERCHANT_CONFIRMATION,
            )
            .order_by("-created_at", "-id")
            .first()
        )
        if not payment:
            raise ValidationError(
                "پرداخت مرتبط برای نهایی‌سازی پیدا نشد.",
                code="missing_payment",
            )

        actor = None
        if store and getattr(store, "merchant", None):
            actor = getattr(store.merchant, "user", None)

        create_event(
            payment_request=request_obj,
            payment=latest_payment,
            actor=actor,
            event_type=PaymentEventType.PAYMENT_VERIFY_REQUESTED,
            from_status=request_obj.status,
            to_status=request_obj.status,
            description="Merchant requested payment verification.",
            extra_data={
                "store_id": store.id if store else None,
            },
        )

        if payment.method == PaymentMethod.CASH:
            settle_cash_payment(payment)
        elif payment.method == PaymentMethod.CREDIT:
            settle_credit_payment(payment)
        else:
            raise ValidationError(
                "روش پرداخت پشتیبانی نمی‌شود.",
                code="unsupported_payment_method",
            )

        from_status = request_obj.status
        payment.mark_completed()
        request_obj.mark_completed(
            user=request_obj.paid_by,
            wallet=request_obj.paid_wallet,
        )
        _log_request_completed_event(
            payment_request=request_obj,
            user=request_obj.paid_by,
            wallet=request_obj.paid_wallet,
            payment=payment,
            from_status=from_status,
        )

        log_event(
            logger,
            level="info",
            event="payment_verification_finished",
            message="Payment verification finished.",
            module="wallets.payment",
            action="verify_payment_request",
            payment_request_id=request_obj.id,
            payment_request_reference=request_obj.reference_code,
            payment_id=payment.id,
            payment_reference=payment.reference_code,
            store_id=request_obj.store_id,
            payment_method=payment.method,
            from_status=from_status,
            to_status=request_obj.status,
        )

        return payment


def rollback_payment(payment_request: PaymentRequest):
    with transaction.atomic():
        request_obj = PaymentRequest.objects.select_for_update().get(
            pk=payment_request.pk
        )

        payment = (
            Payment.objects.select_for_update()
            .filter(payment_request=request_obj)
            .order_by("-created_at", "-id")
            .first()
        )
        if not payment:
            return None

        if payment.status == PaymentStatus.COMPLETED:
            return None

        if payment.method == PaymentMethod.CASH:
            return rollback_cash_payment(payment)

        if payment.method == PaymentMethod.CREDIT:
            return rollback_credit_payment(payment)

        return None
