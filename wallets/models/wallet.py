# wallets/models.py

import random

from django.contrib.auth import get_user_model
from django.db import models, IntegrityError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from wallets.utils.choices import WalletKind, OwnerType, WALLET_KIND_PREFIX


def generate_wallet_number(kind, length=12):
    prefix = WALLET_KIND_PREFIX.get(kind, "60")
    number_length = length - len(prefix)
    while True:
        random_digits = ''.join(
            str(random.randint(0, 9)) for _ in range(number_length)
        )
        wallet_number = f"{prefix}{random_digits}"
        if not Wallet.objects.filter(wallet_number=wallet_number).exists():
            return wallet_number


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
        verbose_name=_("نوع"),
    )
    balance = models.BigIntegerField(
        verbose_name=_("مبلغ"),
        default=0,
    )
    reserved_balance = models.BigIntegerField(
        verbose_name=_("مبلغ رزروشده"),
        default=0
    )
    wallet_number = models.CharField(
        max_length=12,
        unique=True,
        db_index=True,
        verbose_name=_("شماره کیف پول"),
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def available_balance(self) -> int:
        return self.balance - self.reserved_balance

    def save(self, *args, **kwargs):
        if not self.wallet_number:
            for _ in range(5):
                number = generate_wallet_number(self.kind)
                self.wallet_number = number
                try:
                    super().save(*args, **kwargs)
                    break
                except IntegrityError:
                    self.wallet_number = None
            else:
                raise Exception("Failed to generate unique wallet number.")
        else:
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.get_kind_display()} ({self.get_owner_type_display()}) | {self.wallet_number}"

    class Meta:
        unique_together = ("user", "owner_type", "kind")
        verbose_name = _("کیف پول")
        verbose_name_plural = _("کیف پول‌ها")
        constraints = [
            models.CheckConstraint(
                name="balance_non_negative_for_cash_like",
                check=(~Q(kind__in=["cash", "cashback"])) | Q(balance__gte=0),
            ),
        ]
