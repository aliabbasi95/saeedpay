# merchants/models/contract.py

from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from merchants.models.merchant import Merchant


class MerchantContract(BaseModel):
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="contracts",
        verbose_name=_("فروشنده"),
    )
    max_credit_per_user = models.BigIntegerField(
        verbose_name=_("سقف اعتبار برای هر کاربر")
    )
    max_repayment_months = models.PositiveIntegerField(
        verbose_name=_("حداکثر مدت بازپرداخت (ماه)")
    )
    allowed_period_months = models.JSONField(
        default=list,
        help_text="مثلاً [1, 2, 3]",
        verbose_name=_("پریودهای مجاز بازپرداخت (ماه)")
    )
    active = models.BooleanField(
        default=True,
        verbose_name=_("فعال")
    )

    def __str__(self):
        return f"قرارداد فروشگاه {self.merchant.shop_name}"

    class Meta:
        verbose_name = _("قرارداد فروشگاه")
        verbose_name_plural = _("قراردادهای فروشگاه")
