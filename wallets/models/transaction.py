# wallets/models/transaction.py
from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from wallets.models import Wallet, PaymentRequest
from wallets.utils.choices import TransactionStatus


class Transaction(BaseModel):
    from_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="outgoing_transactions",
        verbose_name=_("از کیف پول")
    )
    to_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="incoming_transactions",
        verbose_name = _("به کیف پول")
    )
    amount = models.BigIntegerField(
        verbose_name=_("مبلغ")
    )
    payment_request = models.ForeignKey(
        PaymentRequest,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name = _("مبلغ")
    )
    status = models.CharField(
        max_length=16,
        choices=TransactionStatus.choices,
        default="success",
        verbose_name=_("وضعیت")
    )
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = _("تراکنش کیف پول")
        verbose_name_plural = _("تراکنش‌های کیف پول")
