# tickets/models/category.py

from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel


class TicketCategory(BaseModel):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("نام")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("توضیحات")
    )
    icon = models.CharField(
        max_length=64,
        blank=True,
        verbose_name=_("آیکون")
    )
    color = models.CharField(
        max_length=32,
        blank=True,
        help_text=_("مثال: #1769aa"),
        verbose_name=_("رنگ")
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("دسته‌بندی تیکت")
        verbose_name_plural = _("دسته‌بندی‌های تیکت")
