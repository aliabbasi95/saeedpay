# wallets/models/payment.py
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from wallets.models.wallet import Wallet


class PaymentRequest(BaseModel):
    merchant = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="payment_requests",
        verbose_name=_("فروشنده درخواست‌دهنده")
    )
    amount = models.BigIntegerField(
        verbose_name=_("مبلغ")
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("توضیحات")
    )
    callback_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_("Callback URL")
    )
    is_paid = models.BooleanField(
        default=False,
        verbose_name=_("پرداخت شده")
    )
    paid_by = models.ForeignKey(
        get_user_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="successful_payments",
        verbose_name=_("پرداخت‌کننده")
    )
    paid_wallet = models.ForeignKey(
        Wallet,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("کیف پول پرداخت‌کننده")
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    @property
    def uuid(self):
        return self.guid

    def __str__(self):
        return f"درخواست پرداخت #{self.id} - {self.amount} تومان - توسط {self.merchant}"

    class Meta:
        verbose_name = _("درخواست پرداخت")
        verbose_name_plural = _("درخواست‌های پرداخت")
