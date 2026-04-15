# wallets/services/payment/payment_processing_service.py

from django.db import transaction
from rest_framework.exceptions import ValidationError

from credit.models.authorization import CreditAuthorization
from credit.models.statement import Statement
from credit.models.statement_line import StatementLine
from credit.utils.choices import StatementLineType
from wallets.models import Payment, PaymentRequest, Transaction, Wallet
from wallets.services.payment.payment_request_service import (
    check_and_expire_payment_request,
    ensure_no_active_payment_exists,
    ensure_request_can_be_paid,
    resolve_payment_method,
    validate_payment_request_payer_access,
    validate_wallet_ownership,
)
from wallets.services.payment.payment_shared import (
    build_authorized_event_extra,
    create_event,
    credit_auth_hold_expiry,
    ensure_payment_request_status,
    get_latest_payment_for_request,
    get_escrow_wallet,
    get_merchant_gateway_wallet,
    logger,
    merchant_confirm_expiry,
)
from wallets.utils.choices import (
    PaymentEventType,
    PaymentFlowType,
    PaymentMethod,
    PaymentRequestStatus,
    PaymentStatus,
    TransactionPurpose,
)


def pay_payment_request(request_obj: PaymentRequest, user, wallet: Wallet):
    with transaction.atomic():
        payment_request = (
            PaymentRequest.objects
            .select_for_update()
            .get(pk=request_obj.pk)
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

        payment = Payment.objects.create(
            payment_request=payment_request,
            payer=user,
            payer_wallet=customer_wallet,
            amount=payment_request.amount,
            method=payment_method,
            flow_type=payment_request.flow_type,
            status=PaymentStatus.CREATED,
        )

        if payment.method == PaymentMethod.CASH:
            _authorize_cash_payment(payment, customer_wallet)

            if payment.flow_type == PaymentFlowType.QR_POS:
                _settle_cash_payment(payment)
                payment.mark_completed()
                payment_request.mark_completed_direct(
                    user=user,
                    wallet=customer_wallet,
                )
                _log_request_completed_event(
                    payment_request=payment_request,
                    user=user,
                    wallet=customer_wallet,
                    payment=payment,
                    from_status=PaymentRequestStatus.CREATED,
                )
            else:
                _mark_payment_awaiting_merchant(payment)
                _move_request_to_awaiting_merchant(
                    payment_request=payment_request,
                    user=user,
                    wallet=customer_wallet,
                    merchant_deadline=payment.merchant_confirm_expires_at,
                    payment=payment,
                )

        elif payment.method == PaymentMethod.CREDIT:
            _authorize_credit_payment(payment)

            if payment.flow_type == PaymentFlowType.QR_POS:
                _settle_credit_payment(payment)
                payment.mark_completed()
                payment_request.mark_completed_direct(
                    user=user,
                    wallet=customer_wallet,
                )
                _log_request_completed_event(
                    payment_request=payment_request,
                    user=user,
                    wallet=customer_wallet,
                    payment=payment,
                    from_status=PaymentRequestStatus.CREATED,
                )
            else:
                _mark_payment_awaiting_merchant(payment)
                _move_request_to_awaiting_merchant(
                    payment_request=payment_request,
                    user=user,
                    wallet=customer_wallet,
                    merchant_deadline=payment.merchant_confirm_expires_at,
                    payment=payment,
                )

        return payment


def verify_payment_request(payment_request: PaymentRequest, *, store=None) -> Payment:
    with transaction.atomic():
        request_obj = (
            PaymentRequest.objects
            .select_for_update()
            .get(pk=payment_request.pk)
        )

        if store is not None and request_obj.store_id != store.id:
            raise ValidationError(
                "این درخواست پرداخت متعلق به این فروشگاه نیست.",
                code="forbidden_store",
            )

        if request_obj.flow_type != PaymentFlowType.ONLINE:
            raise ValidationError(
                "نهایی‌سازی برای این نوع درخواست پرداخت مجاز نیست.",
                code="unsupported_flow_type",
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
            _settle_cash_payment(payment)
        elif payment.method == PaymentMethod.CREDIT:
            _settle_credit_payment(payment)
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
            return _rollback_cash_payment(payment)

        if payment.method == PaymentMethod.CREDIT:
            return _rollback_credit_payment(payment)

        return None


def _authorize_cash_payment(payment: Payment, customer_wallet: Wallet):
    escrow_wallet = get_escrow_wallet()

    if customer_wallet.available_balance < payment.amount:
        raise ValidationError(
            "موجودی کافی نیست.",
            code="insufficient_funds",
        )

    customer_wallet.balance -= payment.amount
    escrow_wallet.balance += payment.amount
    customer_wallet.save(update_fields=["balance"])
    escrow_wallet.save(update_fields=["balance"])

    escrow_transaction = Transaction.create_success(
        payment=payment,
        payment_request=payment.payment_request,
        from_wallet=customer_wallet,
        to_wallet=escrow_wallet,
        amount=payment.amount,
        purpose=TransactionPurpose.ESCROW_DEBIT,
        description="Customer → Escrow",
    )

    payment.mark_authorized()

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        transaction=escrow_transaction,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_AUTHORIZED,
        to_status=payment.status,
        description="Cash payment authorized.",
        extra_data=build_authorized_event_extra(
            payment=payment,
            wallet_id=customer_wallet.id,
        ),
    )


def _authorize_credit_payment(payment: Payment):
    from credit.models.credit_limit import CreditLimit

    credit_limit = CreditLimit.objects.get_user_credit_limit(payment.payer)
    if not credit_limit or not credit_limit.is_active:
        raise ValidationError(
            "اعتبار فعال یافت نشد یا منقضی شده است.",
            code="credit_unavailable",
        )
    if int(credit_limit.available_limit) < int(payment.amount):
        raise ValidationError(
            "اعتبار کافی نیست.",
            code="insufficient_credit",
        )

    authorization_expires_at = credit_auth_hold_expiry()

    authorization = CreditAuthorization.objects.create(
        user=payment.payer,
        payment=payment,
        payment_request=payment.payment_request,
        amount=int(payment.amount),
        status=CreditAuthorization.Status.ACTIVE,
        expires_at=authorization_expires_at,
    )

    payment.authorization_expires_at = authorization_expires_at
    payment.mark_authorized()

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_AUTHORIZED,
        to_status=payment.status,
        description="Credit payment authorized.",
        extra_data=build_authorized_event_extra(
            payment=payment,
            wallet_id=payment.payer_wallet_id,
            extra={"credit_authorization_id": authorization.id},
        ),
    )


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


def _settle_cash_payment(payment):
    customer_to_escrow_txn = Transaction.latest_success_for_payment(
        payment,
        TransactionPurpose.ESCROW_DEBIT,
    )
    if not customer_to_escrow_txn:
        raise ValidationError(
            "تراکنش انتقال به امانی برای این پرداخت پیدا نشد.",
            code="missing_escrow_transaction",
        )

    escrow_wallet = Wallet.objects.select_for_update().get(
        pk=customer_to_escrow_txn.to_wallet_id
    )
    merchant_wallet = get_merchant_gateway_wallet(payment)

    if escrow_wallet.balance < payment.amount:
        logger.error(
            "ESCROW low balance verify: need %s, have %s",
            payment.amount,
            escrow_wallet.balance,
        )
        raise ValidationError(
            "عملیات با خطا مواجه شد. لطفاً بعداً تلاش کنید.",
            code="escrow_insufficient",
        )

    escrow_wallet.balance -= payment.amount
    merchant_wallet.balance += payment.amount
    escrow_wallet.save(update_fields=["balance"])
    merchant_wallet.save(update_fields=["balance"])

    settlement_txn = Transaction.create_success(
        payment=payment,
        payment_request=payment.payment_request,
        from_wallet=escrow_wallet,
        to_wallet=merchant_wallet,
        amount=payment.amount,
        purpose=TransactionPurpose.SETTLEMENT,
        description="Escrow → Merchant",
        related_transaction=customer_to_escrow_txn,
    )

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        transaction=settlement_txn,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_SETTLED,
        description="Cash payment settled from escrow to merchant.",
        extra_data={
            "transaction_id": settlement_txn.id,
            "amount": payment.amount,
        },
    )
    return settlement_txn


def _settle_credit_payment(payment: Payment):
    auth = (
        CreditAuthorization.objects.select_for_update()
        .filter(
            payment=payment,
            payment_request=payment.payment_request,
        )
        .order_by("-created_at", "-id")
        .first()
    )
    if not auth:
        raise ValidationError(
            "Authorization not found.",
            code="missing_authorization",
        )

    if auth.status == CreditAuthorization.Status.SETTLED:
        return auth

    if auth.status != CreditAuthorization.Status.ACTIVE:
        raise ValidationError(
            "Authorization is not active.",
            code="invalid_authorization_state",
        )

    auth.status = CreditAuthorization.Status.SETTLED
    auth.save(update_fields=["status"])

    statement, _ = Statement.objects.get_or_create_current_statement(
        payment.payer
    )
    existing_line = StatementLine.all_objects.filter(
        payment=payment,
        type=StatementLineType.PURCHASE,
    ).first()
    if existing_line:
        return auth

    StatementLine.objects.create(
        statement=statement,
        type=StatementLineType.PURCHASE,
        amount=payment.amount,
        payment=payment,
        payment_request=payment.payment_request,
        description=f"Purchase {payment.payment_request.reference_code}",
    )

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_SETTLED,
        description="Credit payment settled.",
        extra_data={
            "credit_authorization_id": auth.id,
            "amount": payment.amount,
        },
    )
    return auth


def _rollback_cash_payment(payment: Payment):
    if Transaction.success_exists_for_payment(payment, TransactionPurpose.REVERSAL):
        return Transaction.latest_success_for_payment(
            payment,
            TransactionPurpose.REVERSAL,
        )

    if Transaction.success_exists_for_payment(payment, TransactionPurpose.SETTLEMENT):
        return None

    debit_transaction = Transaction.latest_success_for_payment(
        payment,
        TransactionPurpose.ESCROW_DEBIT,
    )
    if not debit_transaction:
        return None

    escrow_wallet = Wallet.objects.select_for_update().get(
        pk=debit_transaction.to_wallet_id
    )
    customer_wallet = Wallet.objects.select_for_update().get(
        pk=debit_transaction.from_wallet_id
    )

    if escrow_wallet.balance < debit_transaction.amount:
        logger.error(
            "ESCROW low balance rollback: need %s, have %s",
            debit_transaction.amount,
            escrow_wallet.balance,
        )
        raise ValidationError(
            "عملیات بازگشت وجه با خطا مواجه شد.",
            code="escrow_insufficient",
        )

    escrow_wallet.balance -= debit_transaction.amount
    customer_wallet.balance += debit_transaction.amount
    escrow_wallet.save(update_fields=["balance"])
    customer_wallet.save(update_fields=["balance"])

    reversal = Transaction.create_success(
        payment=payment,
        payment_request=payment.payment_request,
        related_transaction=debit_transaction,
        from_wallet=escrow_wallet,
        to_wallet=customer_wallet,
        amount=debit_transaction.amount,
        purpose=TransactionPurpose.REVERSAL,
        description="Escrow → Customer (reversal)",
    )

    if payment.payment_request.status == PaymentRequestStatus.CANCELLED:
        payment.mark_cancelled()
        reason_code = "rollback_after_cancel"
    elif payment.payment_request.status == PaymentRequestStatus.EXPIRED:
        payment.mark_expired()
        reason_code = "rollback_after_expire"
    else:
        reason_code = "rollback_generic"

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        transaction=reversal,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_ROLLBACK,
        to_status=payment.status,
        description="Cash payment rolled back.",
        extra_data={
            "reason_code": reason_code,
            "rollback_type": "cash_reversal",
            "transaction_id": reversal.id,
            "amount": reversal.amount,
            "payment_status": payment.status,
            "payment_request_status": payment.payment_request.status,
        },
    )
    return reversal


def _rollback_credit_payment(payment: Payment):
    auth = (
        CreditAuthorization.objects.select_for_update()
        .filter(
            payment=payment,
            payment_request=payment.payment_request,
        )
        .order_by("-created_at", "-id")
        .first()
    )
    if not auth:
        return None

    if auth.status == CreditAuthorization.Status.ACTIVE:
        auth.status = CreditAuthorization.Status.RELEASED
        auth.save(update_fields=["status"])

    if payment.payment_request.status == PaymentRequestStatus.CANCELLED:
        payment.mark_cancelled()
        reason_code = "rollback_after_cancel"
    elif payment.payment_request.status == PaymentRequestStatus.EXPIRED:
        payment.mark_expired()
        reason_code = "rollback_after_expire"
    else:
        reason_code = "credit_authorization_released"

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_ROLLBACK,
        to_status=payment.status,
        description="Credit authorization released / rolled back.",
        extra_data={
            "reason_code": reason_code,
            "rollback_type": "credit_release",
            "credit_authorization_id": auth.id,
            "amount": payment.amount,
            "payment_status": payment.status,
            "payment_request_status": payment.payment_request.status,
        },
    )
    return auth
