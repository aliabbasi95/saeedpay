# store/models/contract.py

from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import dynamic_cardboard
from store.models.store import Store


class StoreContract(
    dynamic_cardboard(
        [("contract_reviewer", "کارشناس بررسی قرارداد")],
        'store_contract',
    )
):
    store = models.OneToOneField(
        Store,
        on_delete=models.CASCADE,
        related_name="contract",
        verbose_name=_("فروشگاه"),
    )
    max_credit_per_user = models.BigIntegerField(
        verbose_name=_("سقف اعتبار برای هر کاربر")
    )
    min_credit_per_user = models.BigIntegerField(
        default=0,
        verbose_name=_("حداقل اعتبار برای هر کاربر")
    )
    max_repayment_months = models.PositiveIntegerField(
        verbose_name=_("حداکثر مدت بازپرداخت (ماه)")
    )
    min_repayment_months = models.PositiveIntegerField(
        default=1,
        verbose_name=_("حداقل مدت بازپرداخت (ماه)")
    )
    allowed_period_months = models.JSONField(
        default=list,
        help_text="مثلاً [1, 2, 3]",
        verbose_name=_("پریودهای مجاز بازپرداخت (ماه)")
    )
    interest_rate = models.FloatField(
        default=0.0,
        help_text="نرخ بهره سالیانه (درصد)، به عنوان مثال: 18.0",
        verbose_name=_("نرخ بهره سالیانه (٪)")
    )
    callback_url = models.URLField(
        verbose_name=_("آدرس callback برای اطلاع تایید کاربر"),
    )
    active = models.BooleanField(
        default=True,
        verbose_name=_("فعال")
    )

    def save(self, *args, **kwargs):
        if not self.store.status or self.store.status < len(
                self.store.ROLES
        ) + 1:
            raise Exception(
                "قرارداد فقط برای فروشگاه‌های تاییدشده قابل ثبت است."
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"قرارداد فروشگاه {self.store.name}"

    class Meta:
        verbose_name = _("قرارداد فروشگاه")
        verbose_name_plural = _("قراردادهای فروشگاه")
