# store/models/store.py

from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import dynamic_cardboard
from merchants.models import Merchant


class Store(
    dynamic_cardboard(
        [("store_reviewer", "کارشناس بررسی فروشگاه"), ],
        'store',
    )
):
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="stores",
        verbose_name=_("فروشنده")
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_("نام فروشگاه")
    )
    code = models.CharField(
        null=True,
        blank=True,
        max_length=20,
        unique=True,
        verbose_name=_("کد فروشگاه")
    )
    address = models.TextField(
        blank=True,
        verbose_name=_("آدرس")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("فعال است؟")
    )

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        verbose_name = _("فروشگاه")
        verbose_name_plural = _("فروشگاه‌ها")
