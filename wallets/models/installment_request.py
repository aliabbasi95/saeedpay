# wallets/models/installment_request.py

from django.db import models
from django.utils.translation import gettext_lazy as _

from customers.models import Customer
from lib.erp_base.models import BaseModel
from merchants.models import Merchant, MerchantContract
from wallets.utils.choices import InstallmentRequestStatus


class InstallmentRequest(BaseModel):
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE,
        related_name="installment_requests",
        verbose_name=_("فروشگاه")
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE,
        related_name="installment_requests",
        verbose_name=_("مشتری")
    )
    national_id = models.CharField(
        max_length=10,
        verbose_name=_("کد ملی")
    )
    requested_amount = models.BigIntegerField(
        verbose_name=_("مبلغ درخواستی")
    )
    approved_amount = models.BigIntegerField(
        null=True, blank=True,
        verbose_name=_("مبلغ تایید شده")
    )
    contract = models.ForeignKey(
        MerchantContract,
        on_delete=models.PROTECT,
        related_name="installment_requests",
        verbose_name=_("قرارداد استفاده شده")
    )
    duration_months = models.PositiveIntegerField(
        verbose_name=_("مدت بازپرداخت (ماه)")
    )
    period_days = models.PositiveIntegerField(
        verbose_name=_("پریود بازپرداخت (روز)")
    )
    status = models.CharField(
        max_length=32,
        choices=InstallmentRequestStatus.choices,
        default=InstallmentRequestStatus.CREATED,
        verbose_name=_("وضعیت")
    )
    user_confirmed_at = models.DateTimeField(null=True, blank=True)
    merchant_confirmed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.customer} - {self.requested_amount} تومان ({self.get_status_display()})"

    class Meta:
        verbose_name = _("درخواست خرید اقساطی")
        verbose_name_plural = _("درخواست‌های خرید اقساطی")
