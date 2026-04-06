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


class PaymentFlowType(models.TextChoices):
    ONLINE = "online", _("آنلاین")
    QR_POS = "qr_pos", _("حضوری QR")


class PaymentMethod(models.TextChoices):
    CASH = "cash", _("نقدی")
    CREDIT = "credit", _("اعتباری")


class PaymentStatus(models.TextChoices):
    CREATED = "created", _("ایجاد شده")
    AUTHORIZED = "authorized", _("مجاز/هولد شده")
    AWAITING_MERCHANT_CONFIRMATION = "awaiting_merchant", _(
        "در انتظار تایید فروشگاه"
    )
    COMPLETED = "completed", _("تکمیل شده")
    CANCELLED = "cancelled", _("لغو شده")
    EXPIRED = "expired", _("منقضی شده")
    FAILED = "failed", _("ناموفق")


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


class TransactionPurpose(models.TextChoices):
    ESCROW_DEBIT = "escrow_debit", _("انتقال به امانی (Escrow)")
    SETTLEMENT = "settlement", _("تسویه با فروشنده")
    REVERSAL = "reversal", _("بازگشت وجه")


class TransferStatus(models.TextChoices):
    PENDING_CONFIRMATION = "pending_confirmation", "در انتظار تایید گیرنده"
    SUCCESS = "success", "انجام شده"
    REJECTED = "rejected", "رد شده"
    EXPIRED = "expired", "منقضی شده"


class InstallmentPlanStatus(models.TextChoices):
    ACTIVE = "active", _("فعال")
    COMPLETED = "completed", _("پرداخت‌شده کامل")
    CANCELLED = "cancelled", _("لغو شده")


class InstallmentSourceType(models.TextChoices):
    BNPL = "bnpl", _("درخواست فروشگاه (BNPL)")
    PAYMENT_REQUEST = "payment_request", _("پرداخت با اعتبار داخلی")


class InstallmentStatus(models.TextChoices):
    UNPAID = "unpaid", _("پرداخت‌نشده")
    PAID = "paid", _("پرداخت‌شده")
    OVERDUE = "overdue", _("سررسید گذشته")


class PaymentEventType(models.TextChoices):
    PAYMENT_REQUEST_CREATED = "payment_request_created", "درخواست پرداخت ایجاد شد"
    PAYMENT_AUTHORIZED = "payment_authorized", "پرداخت مجاز شد"
    AWAITING_MERCHANT = "awaiting_merchant", "در انتظار تایید فروشگاه"
    PAYMENT_SETTLED = "payment_settled", "تسویه انجام شد"
    PAYMENT_COMPLETED = "payment_completed", "پرداخت تکمیل شد"
    PAYMENT_CANCELLED = "payment_cancelled", "پرداخت لغو شد"
    PAYMENT_EXPIRED = "payment_expired", "پرداخت منقضی شد"
    PAYMENT_ROLLBACK = "payment_rollback", "بازگشت وجه/آزادسازی انجام شد"
    PAYMENT_VERIFY_REQUESTED = "payment_verify_requested", "درخواست نهایی‌سازی ثبت شد"
