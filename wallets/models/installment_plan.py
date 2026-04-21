# wallets/models/installment_plan.py

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from wallets.utils.choices import InstallmentPlanStatus, InstallmentSourceType


class InstallmentPlan(BaseModel):
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="installment_plans",
        verbose_name=_("کاربر"),
    )

    source_type = models.CharField(
        max_length=32,
        choices=InstallmentSourceType.choices,
        verbose_name=_("نوع منبع"),
    )
    source_object_id = models.PositiveBigIntegerField(verbose_name=_("شناسه مرجع منبع"))

    total_amount = models.BigIntegerField(verbose_name=_("مبلغ کل قابل پرداخت"))
    duration_months = models.PositiveIntegerField(verbose_name=_("مدت بازپرداخت (ماه)"))
    period_months = models.PositiveIntegerField(
        verbose_name=_("پریود پرداخت اقساط (ماه)")
    )
    interest_rate = models.FloatField(verbose_name=_("نرخ بهره سالیانه (٪)"))

    initial_transaction = models.ForeignKey(
        "wallets.Transaction",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="installment_plans",
        verbose_name=_("تراکنش اولیه مرتبط"),
    )
    description = models.TextField(blank=True, verbose_name=_("توضیحات"))
    created_by = models.CharField(
        max_length=32,
        default="system",
        verbose_name=_("ایجاد شده توسط"),
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("زمان بستن"),
    )

    status = models.CharField(
        max_length=16,
        choices=InstallmentPlanStatus.choices,
        default=InstallmentPlanStatus.ACTIVE,
        verbose_name=_("وضعیت"),
    )

    def get_source_object(self):
        if self.source_type == InstallmentSourceType.PAYMENT_REQUEST:
            from wallets.models.payment_request import PaymentRequest

            return PaymentRequest.objects.filter(id=self.source_object_id).first()

        # if self.source_type == InstallmentSourceType.OFFLINE_PURCHASE:
        #     from wallets.models.offline_purchase import OfflinePurchaseRecord
        #     return OfflinePurchaseRecord.objects.filter(
        #         id=self.source_object_id
        #     ).first()

        # if self.source_type == InstallmentSourceType.STORE_ORDER:
        #     from wallets.models.store_order import StoreOrder
        #     return StoreOrder.objects.filter(id=self.source_object_id).first()

        return None

    def __str__(self):
        return f"Plan #{self.id} for {self.user} - {self.total_amount} ریال"

    class Meta:
        indexes = [
            models.Index(fields=["user", "-created_at"], name="iplan_user_created_idx"),
        ]
        verbose_name = _("برنامه اقساطی")
        verbose_name_plural = _("برنامه‌های اقساطی")
