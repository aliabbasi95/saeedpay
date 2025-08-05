# merchants/models/merchant.py
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel


class Merchant(BaseModel):
    user = models.OneToOneField(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="merchant",
        verbose_name=_("کاربر")
    )

    class Meta:
        verbose_name = _("فروشنده")
        verbose_name_plural = _("فروشنده‌ها")

    def __str__(self):
        return f"فروشنده: ({self.user.username})"
