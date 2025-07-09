# wallets/utils/choices.py
from django.db import models
from django.utils.translation import gettext_lazy as _


class WalletKind(models.TextChoices):
    MICRO_CREDIT = "micro_credit", _("اعتباری خرد")
    CASH = "cash", _("نقدی")
    CASHBACK = "cashback", _("بازگشت پول")
    CREDIT = "credit", _("اعتباری")
    MERCHANT_GATEWAY = "merchant_gateway", _("درگاه فروشگاه")


class OwnerType(models.TextChoices):
    CUSTOMER = "customer", _("مشتری")
    MERCHANT = "merchant", _("فروشنده")


class TransactionStatus(models.TextChoices):
    SUCCESS = "success", _("موفق")
    FAILED = "failed", _("ناموفق")
