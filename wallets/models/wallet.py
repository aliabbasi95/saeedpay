# wallets/models.py
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from wallets.utils.choices import WalletKind, OwnerType


class Wallet(BaseModel):
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name="wallets"
    )
    owner_type = models.CharField(max_length=20, choices=OwnerType.choices)

    kind = models.CharField(max_length=20, choices=WalletKind.choices)

    balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "owner_type", "kind")
        verbose_name = _("کیف پول")
        verbose_name_plural = _("کیف پول‌ها")

    def __str__(self):
        return f"{self.user.username} - {self.get_kind_display()} ({self.get_owner_type_display()})"
