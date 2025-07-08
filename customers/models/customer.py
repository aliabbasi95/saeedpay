# customers/models/customer.py
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel


class Customer(BaseModel):
    user = models.OneToOneField(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="customer",
        verbose_name="کاربر"
    )

    class Meta:
        verbose_name = _("مشتری")
        verbose_name_plural = _("مشتری‌ها")

    def __str__(self):
        return f"مشتری: ({self.user.username})"
