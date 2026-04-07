# wallets/services/payment/payment_shared.py

import logging
from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from wallets.models import Payment, Wallet
from wallets.services.payment.payment_event import create_payment_event
from wallets.utils.choices import (
    OwnerType,
    PaymentMethod,
    PaymentRequestStatus,
    WalletKind,
)
from wallets.utils.consts import (
    CREDIT_AUTH_HOLD_EXPIRY_MINUTES,
    ESCROW_USER_NAME,
    ESCROW_WALLET_KIND,
    MERCHANT_CONFIRM_WINDOW_MINUTES,
)

logger = logging.getLogger(__name__)


def now_local():
    return timezone.localtime(timezone.now())


def credit_auth_hold_expiry():
    return now_local() + timedelta(minutes=CREDIT_AUTH_HOLD_EXPIRY_MINUTES)


def merchant_confirm_expiry():
    return now_local() + timedelta(minutes=MERCHANT_CONFIRM_WINDOW_MINUTES)


def is_terminal_payment_request_status(status: str) -> bool:
    return status in {
        PaymentRequestStatus.COMPLETED,
        PaymentRequestStatus.CANCELLED,
        PaymentRequestStatus.EXPIRED,
    }


def get_latest_payment_for_request(payment_request):
    return (
        Payment.objects.select_for_update()
        .filter(payment_request=payment_request)
        .order_by("-created_at", "-id")
        .first()
    )


def ensure_payment_request_status(
        payment_request,
        *,
        allowed_statuses: set[str],
        error_message: str,
        error_code: str = "invalid_state",
):
    if payment_request.status not in allowed_statuses:
        raise ValidationError(error_message, code=error_code)


def create_event(
        *,
        payment_request,
        event_type,
        payment=None,
        transaction=None,
        actor=None,
        from_status=None,
        to_status=None,
        description="",
        extra_data=None,
):
    create_payment_event(
        payment_request=payment_request,
        payment=payment,
        transaction=transaction,
        actor=actor,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        description=description,
        extra_data=extra_data or {},
    )


def get_payment_method_from_wallet(wallet: Wallet) -> str:
    if wallet.kind == WalletKind.CASH:
        return PaymentMethod.CASH
    if wallet.kind == WalletKind.CREDIT:
        return PaymentMethod.CREDIT
    raise ValidationError(
        "نوع کیف پول مجاز نیست.",
        code="unsupported_wallet",
    )


def get_escrow_wallet():
    return Wallet.objects.select_for_update().get(
        user__username=ESCROW_USER_NAME,
        kind=ESCROW_WALLET_KIND,
    )


def get_merchant_gateway_wallet(payment):
    try:
        return Wallet.objects.select_for_update().get(
            user=payment.payment_request.store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
        )
    except Wallet.DoesNotExist:
        raise ValidationError(
            "کیف پول فروشگاه برای تسویه یافت نشد.",
            code="merchant_wallet_not_found",
        )


def build_authorized_event_extra(*, payment, wallet_id=None, extra=None):
    payload = {
        "amount": payment.amount,
        "payment_method": payment.method,
        "flow_type": payment.flow_type,
        "wallet_id": wallet_id,
    }
    if extra:
        payload.update(extra)
    return payload
