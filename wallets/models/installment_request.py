# wallets/models/installment_request.py

from django.db import models
from django.utils.translation import gettext_lazy as _

from customers.models import Customer
from lib.erp_base.models import BaseModel
from store.models import Store, StoreContract
from wallets.utils.choices import (
    InstallmentRequestStatus,
    InstallmentSourceType,
)
from wallets.utils.reference import generate_reference_code


class InstallmentRequest(BaseModel):
    store = models.ForeignKey(
        Store,
        null=True,
        on_delete=models.CASCADE,
        related_name="installment_requests",
        verbose_name=_("فروشگاه")
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE,
        related_name="installment_requests",
        verbose_name=_("مشتری")
    )
    reference_code = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_("کد پیگیری")
    )
    national_id = models.CharField(
        max_length=10,
        verbose_name=_("کد ملی")
    )
    proposal_amount = models.BigIntegerField(
        verbose_name=_("مبلغ پیشنهادی فروشگاه")
    )
    confirmed_amount = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name=_("مبلغ تایید شده توسط مشتری")
    )
    contract = models.ForeignKey(
        StoreContract,
        on_delete=models.PROTECT,
        related_name="installment_requests",
        verbose_name=_("قرارداد فروشگاه")
    )
    duration_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("مدت بازپرداخت (ماه)")
    )
    period_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("پریود بازپرداخت (ماه)")
    )
    status = models.CharField(
        max_length=32,
        choices=InstallmentRequestStatus.choices,
        default=InstallmentRequestStatus.CREATED,
        verbose_name=_("وضعیت")
    )
    user_confirmed_at = models.DateTimeField(null=True, blank=True)
    store_confirmed_at = models.DateTimeField(null=True, blank=True)
    external_guid = models.CharField(
        max_length=64,
        verbose_name=_("شناسه خارجی (سیستم فروشگاه)"),
        help_text="GUID اختصاصی ارسال‌شده از سیستم فروشگاه"
    )

    def save(self, *args, **kwargs):
        if not self.reference_code:
            for _ in range(5):
                code = generate_reference_code(prefix="INST", random_digits=6)
                if not InstallmentRequest.objects.filter(
                        reference_code=code
                ).exists():
                    self.reference_code = code
                    break
            else:
                raise Exception(
                    "Reference code generation failed. Please try again."
                )
        super().save(*args, **kwargs)

    def get_installment_plan(self):
        from wallets.models import InstallmentPlan
        return InstallmentPlan.objects.filter(
            source_type=InstallmentSourceType.BNPL,
            source_object_id=self.id
        ).first()

    def __str__(self):
        return f"{self.customer} - {self.proposal_amount} ریال ({self.get_status_display()})"

    class Meta:
        verbose_name = _("درخواست خرید اقساطی")
        verbose_name_plural = _("درخواست‌های خرید اقساطی")
