# banking/models/bank.py

from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel


class Bank(BaseModel):
    name = models.CharField(
        max_length=100,
        verbose_name=_("نام بانک"),
    )
    logo = models.ImageField(
        upload_to="banks/logos/",
        blank=True,
        null=True,
        verbose_name=_("لوگوی بانک"),
    )
    color = models.CharField(
        max_length=7,
        help_text=_("کد رنگ هگز، مانند ‎#1E88E5"),
        verbose_name=_("رنگ برند"),
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]
        verbose_name = _("بانک")
        verbose_name_plural = _("بانک‌ها")
