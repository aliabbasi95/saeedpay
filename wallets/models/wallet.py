# wallets/models.py
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from wallets.utils.choices import WalletKind, OwnerType


class Wallet(BaseModel):
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="wallets",
        verbose_name="کاربر"
    )
    owner_type = models.CharField(
        max_length=20,
        choices=OwnerType.choices,
        verbose_name="نوع کاربر"
    )
    kind = models.CharField(
        max_length=20,
        choices=WalletKind.choices,
        verbose_name = _("نوع")
    )
    balance = models.BigIntegerField(
        verbose_name=_("مبلغ")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "owner_type", "kind")
        verbose_name = _("کیف پول")
        verbose_name_plural = _("کیف پول‌ها")

    def __str__(self):
        return f"{self.user.username} - {self.get_kind_display()} ({self.get_owner_type_display()})"
