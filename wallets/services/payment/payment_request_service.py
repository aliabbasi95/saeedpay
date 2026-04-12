# wallets/services/payment/payment_request_service.py

from django.db import transaction
from rest_framework.exceptions import ValidationError

from wallets.models import PaymentRequest, Wallet
from wallets.services.payment.payment_shared import (
    create_event,
    credit_auth_hold_expiry,
    ensure_payment_request_status,
    get_latest_payment_for_request,
    get_payment_method_from_wallet,
    is_terminal_payment_request_status,
    now_local,
)
from wallets.utils.choices import (
    OwnerType,
    PaymentEventType,
    PaymentFlowType,
    PaymentRequestStatus,
    PaymentStatus,
    WalletKind,
)


def _validate_payment_request_creation(
        *,
        flow_type,
        return_url,
        external_guid,
):
    if flow_type == PaymentFlowType.ONLINE:
        if not return_url:
            raise ValidationError(
                "return_url برای پرداخت آنلاین الزامی است.",
                code="return_url_required",
            )
        if not external_guid:
            raise ValidationError(
                "external_guid برای پرداخت آنلاین الزامی است.",
                code="external_guid_required",
            )
        return

    if flow_type == PaymentFlowType.QR_POS:
        if return_url:
            raise ValidationError(
                "return_url در پرداخت حضوری QR نباید ارسال شود.",
                code="return_url_not_allowed",
            )
        if external_guid:
            raise ValidationError(
                "external_guid در پرداخت حضوری QR نباید ارسال شود.",
                code="external_guid_not_allowed",
            )
        return


def create_payment_request(
        store,
        amount,
        return_url=None,
        customer=None,
        description="",
        external_guid=None,
        flow_type=PaymentFlowType.ONLINE,
        actor=None,
):
    _validate_payment_request_creation(
        flow_type=flow_type,
        return_url=return_url,
        external_guid=external_guid,
    )

    created_deadline = credit_auth_hold_expiry()

    payment_request = PaymentRequest.objects.create(
        store=store,
        amount=amount,
        customer=customer,
        status=PaymentRequestStatus.CREATED,
        description=description,
        return_url=return_url,
        external_guid=external_guid,
        flow_type=flow_type,
        created_expires_at=created_deadline,
        expires_at=created_deadline,
    )

    create_event(
        payment_request=payment_request,
        event_type=PaymentEventType.PAYMENT_REQUEST_CREATED,
        actor=actor if actor is not None else getattr(customer, "user", None),
        to_status=payment_request.status,
        description="Payment request created.",
        extra_data={
            "amount": payment_request.amount,
            "flow_type": payment_request.flow_type,
            "store_id": payment_request.store_id,
        },
    )
    return payment_request


def list_eligible_wallets_for_payment_request(user, payment_request):
    wallets = Wallet.objects.filter(
        user=user,
        owner_type=OwnerType.CUSTOMER,
    ).order_by("kind")

    eligible_ids = []

    for wallet in wallets:
        if wallet.kind == WalletKind.CASH:
            if int(wallet.available_balance or 0) >= int(payment_request.amount):
                eligible_ids.append(wallet.id)
        elif wallet.kind == WalletKind.CREDIT:
            from credit.models.credit_limit import CreditLimit

            credit_limit = CreditLimit.objects.get_user_credit_limit(user)
            if (
                    credit_limit
                    and getattr(credit_limit, "is_active", False)
                    and getattr(credit_limit, "available_limit", 0) >= int(
                payment_request.amount
            )
            ):
                eligible_ids.append(wallet.id)

    return wallets.filter(id__in=eligible_ids)


def check_and_expire_payment_request(
        payment_request: PaymentRequest,
        *,
        raise_exception: bool = True,
) -> bool:
    payment_request = PaymentRequest.objects.get(pk=payment_request.pk)

    if payment_request.expires_at and payment_request.expires_at < now_local():
        if not is_terminal_payment_request_status(payment_request.status):
            expire_payment_request(payment_request)

        if raise_exception:
            raise ValidationError(
                detail="درخواست پرداخت منقضی شده است.",
                code="expired",
            )
        return True

    return False


def expire_payment_request(payment_request: PaymentRequest):
    from wallets.services.payment.payment_processing_service import rollback_payment

    with transaction.atomic():
        request_obj = PaymentRequest.objects.select_for_update().get(
            pk=payment_request.pk
        )

        if request_obj.status == PaymentRequestStatus.EXPIRED:
            return request_obj

        if request_obj.status in {
            PaymentRequestStatus.CANCELLED,
            PaymentRequestStatus.COMPLETED,
        }:
            return request_obj

        from_status = request_obj.status
        request_obj.mark_expired()
        rollback_payment(request_obj)

        latest_payment = get_latest_payment_for_request(request_obj)
        create_event(
            payment_request=request_obj,
            payment=latest_payment,
            actor=request_obj.paid_by,
            event_type=PaymentEventType.PAYMENT_EXPIRED,
            from_status=from_status,
            to_status=request_obj.status,
            description="Payment request expired.",
        )
        return request_obj


def cancel_payment_request(
        payment_request: PaymentRequest,
        *,
        store=None,
        actor=None,
):
    from wallets.services.payment.payment_processing_service import rollback_payment

    with transaction.atomic():
        request_obj = (
            PaymentRequest.objects.select_for_update()
            .select_related("store__merchant__user", "paid_by")
            .get(pk=payment_request.pk)
        )

        if store is not None and request_obj.store_id != store.id:
            raise ValidationError(
                "این درخواست پرداخت متعلق به این فروشگاه نیست.",
                code="forbidden_store",
            )

        if request_obj.status == PaymentRequestStatus.CANCELLED:
            return request_obj

        if request_obj.status in {
            PaymentRequestStatus.EXPIRED,
            PaymentRequestStatus.COMPLETED,
        }:
            raise ValidationError(
                "این درخواست پرداخت در وضعیت فعلی قابل لغو نیست.",
                code="not_cancellable",
            )

        from_status = request_obj.status
        request_obj.mark_cancelled()
        rollback_payment(request_obj)

        latest_payment = get_latest_payment_for_request(request_obj)
        create_event(
            payment_request=request_obj,
            payment=latest_payment,
            actor=actor if actor is not None else request_obj.paid_by,
            event_type=PaymentEventType.PAYMENT_CANCELLED,
            from_status=from_status,
            to_status=request_obj.status,
            description="Payment request cancelled.",
            extra_data={
                "store_id": request_obj.store_id,
                "flow_type": request_obj.flow_type,
            },
        )
        return request_obj


def validate_wallet_ownership(*, user, wallet):
    customer_wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

    if (
            customer_wallet.user_id != user.id
            or customer_wallet.owner_type != OwnerType.CUSTOMER
    ):
        raise ValidationError(
            "کیف پول برای کاربر نیست.",
            code="wallet_not_owned",
        )

    return customer_wallet


def validate_payment_request_payer_access(*, payment_request, user):
    bound_customer = getattr(payment_request, "customer", None)

    if not bound_customer:
        return

    user_customer = getattr(user, "customer", None)
    if not user_customer or user_customer.id != bound_customer.id:
        raise ValidationError(
            "این درخواست پرداخت برای شما نیست.",
            code="payment_request_not_allowed",
        )


def ensure_request_can_be_paid(payment_request):
    ensure_payment_request_status(
        payment_request,
        allowed_statuses={PaymentRequestStatus.CREATED},
        error_message="پرداخت در این وضعیت قابل انجام نیست.",
    )


def ensure_no_active_payment_exists(payment_request):
    existing_payment = (
        payment_request.payments.select_for_update()
        .filter(
            status__in=[
                PaymentStatus.CREATED,
                PaymentStatus.AUTHORIZED,
                PaymentStatus.AWAITING_MERCHANT_CONFIRMATION,
                PaymentStatus.COMPLETED,
            ],
        )
        .order_by("-created_at", "-id")
        .first()
    )
    if existing_payment:
        raise ValidationError(
            "این درخواست پرداخت قبلاً پردازش شده است.",
            code="already_processed",
        )
    return existing_payment


def resolve_payment_method(wallet):
    return get_payment_method_from_wallet(wallet)
