# wallets/utils/choices.py
from django.db import models
from django.utils.translation import gettext_lazy as _


class WalletKind(models.TextChoices):
    MICRO_CREDIT = "micro_credit", _("اعتباری خرد")
    CASH = "cash", _("نقدی")
    CREDIT = "credit", _("اعتباری")
    CASHBACK = "cashback", _("بازگشت پول")
    MERCHANT_GATEWAY = "merchant_gateway", _("درگاه فروشگاه")
    ESCROW = "escrow", "escrow"


WALLET_KIND_PREFIX = {
    "micro_credit": "50",
    "cash": "60",
    "credit": "61",
    "cashback": "62",
    "merchant_gateway": "63",
    "escrow": "99",
}


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


class InstallmentRequestStatus(models.TextChoices):
    CREATED = "created", _("در انتظار ورود شرایط توسط کاربر")
    UNDERWRITING = "underwriting", _("در انتظار نتیجه اعتبارسنجی")
    VALIDATED = "validated", _("اعتبارسنجی شد؛ منتظر تایید کاربر")
    AWAITING_MERCHANT_CONFIRMATION = "awaiting_merchant", _(
        "در انتظار تایید فروشنده"
    )
    COMPLETED = "completed", _("تایید نهایی انجام شد")
    CANCELLED = "cancelled", _("لغو شده")
    REJECTED = "rejected", _("رد شده")


class InstallmentPlanStatus(models.TextChoices):
    ACTIVE = "active", _("فعال")
    COMPLETED = "completed", _("پرداخت‌شده کامل")
    CANCELLED = "cancelled", _("لغو شده")


class InstallmentSourceType(models.TextChoices):
    BNPL = "bnpl", _("درخواست فروشگاه (BNPL)")
    PAYMENT_REQUEST = "payment_request", _("پرداخت با اعتبار داخلی")
    # OFFLINE_PURCHASE = "offline", _("خرید حضوری")
    # STORE_ORDER = "store_order", _("سفارش فروشگاه داخلی")


class InstallmentStatus(models.TextChoices):
    UNPAID = "unpaid", _("پرداخت‌نشده")
    PAID = "paid", _("پرداخت‌شده")
    OVERDUE = "overdue", _("سررسید گذشته")
