# wallets/utils/choices.py
from django.db import models
from django.utils.translation import gettext_lazy as _


class WalletKind(models.TextChoices):
    MICRO_CREDIT = "micro_credit", _("اعتباری خرد")
    CASH = "cash", _("نقدی")
    CASHBACK = "cashback", _("بازگشت پول")
    CREDIT = "credit", _("اعتباری")
    MERCHANT_GATEWAY = "merchant_gateway", _("درگاه فروشگاه")
    ESCROW = "escrow", "escrow"


class OwnerType(models.TextChoices):
    CUSTOMER = "customer", _("مشتری")
    MERCHANT = "merchant", _("فروشنده")
    SYSTEM = "system", _("سیستم")


class PaymentRequestStatus(models.TextChoices):
    CREATED = "created", _("در انتظار پرداخت کاربر")
    AWAITING_MERCHANT_CONFIRMATION = "awaiting_merchant", _(
        "در انتظار تایید فروشنده"
    )
    COMPLETED = "completed", _("پرداخت نهایی شده")
    CANCELLED = "cancelled", _("لغو شده")
    EXPIRED = "expired", _("منقضی شده")


class TransactionStatus(models.TextChoices):
    PENDING = "pending", "در انتظار تایید"
    SUCCESS = "success", "موفق"
    FAILED = "failed", "ناموفق"
    REVERSED = "reversed", "برگشت‌خورده"


class TransferStatus(models.TextChoices):
    PENDING_CONFIRMATION = "pending_confirmation", "در انتظار تایید گیرنده"
    SUCCESS = "success", "انجام شده"
    REJECTED = "rejected", "رد شده"
    EXPIRED = "expired", "منقضی شده"
