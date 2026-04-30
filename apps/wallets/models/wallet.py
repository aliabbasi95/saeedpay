# apps/wallets/models/wallet.py

import random

from django.contrib.auth import get_user_model
from django.db import IntegrityError, models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.wallets.utils.choices import WALLET_KIND_PREFIX, OwnerType, WalletKind
from lib.erp_base.models import BaseModel


def generate_wallet_number(kind: str, length: int = 12) -> str:
    prefix = WALLET_KIND_PREFIX.get(kind, "60")
    number_length = length - len(prefix)
    random_digits = "".join(str(random.randint(0, 9)) for _ in range(number_length))
    return f"{prefix}{random_digits}"


class Wallet(BaseModel):
    WALLET_NUMBER_MAX_RETRIES = 5

    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="wallets",
        verbose_name="کاربر",
    )
    owner_type = models.CharField(
        max_length=20,
        choices=OwnerType.choices,
        verbose_name="نوع کاربر",
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
        default=0,
    )
    wallet_number = models.CharField(
        max_length=12,
        unique=True,
        db_index=True,
        verbose_name=_("شماره کیف پول"),
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def available_balance(self) -> int:
        return self.balance - self.reserved_balance

    def _save_with_generated_wallet_number(self, *args, **kwargs):
        for _attempt in range(self.WALLET_NUMBER_MAX_RETRIES):
            self.wallet_number = generate_wallet_number(self.kind)

            try:
                super().save(*args, **kwargs)
                return
            except IntegrityError as exc:
                if "wallet_number" not in str(exc).lower():
                    raise

                self.wallet_number = ""

        raise IntegrityError("Failed to generate unique wallet number after retries.")

    def save(self, *args, **kwargs):
        if self.wallet_number:
            super().save(*args, **kwargs)
            return

        self._save_with_generated_wallet_number(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.get_kind_display()} "
            f"({self.get_owner_type_display()}) | "
            f"{self.wallet_number}"
        )

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
