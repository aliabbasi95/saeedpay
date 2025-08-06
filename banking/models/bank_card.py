"""
Defines the BankCard model for storing user bank card information.
"""

import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from banking.utils.choices import BankCardStatus
from .bank import Bank


class BankCard(models.Model):
    """
    Represents a user's bank card.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bank_cards",
        verbose_name=_("User"),
    )
    bank = models.ForeignKey(
        Bank,
        on_delete=models.CASCADE,
        related_name="cards",
        verbose_name=_("Bank"),
        null=True,
        blank=True,
    )
    card_number = models.CharField(
        max_length=16,
        verbose_name=_("Card Number"),
        # In a real application, this should be encrypted.
        # Consider using a library like django-cryptography.
    )
    card_holder_name = models.CharField(
        max_length=70, verbose_name=_("Card Holder Name"), blank=True
    )
    is_default = models.BooleanField(
        default=False, verbose_name=_("Is Default")
    )
    status = models.CharField(
        max_length=20,
        choices=BankCardStatus.choices,
        default=BankCardStatus.PENDING,
        verbose_name=_("Status"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    sheba = models.CharField(
        max_length=26, blank=True, null=True, verbose_name=_("Sheba")
    )
    added_at = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Added At")
    )
    last_used = models.DateTimeField(
        blank=True, null=True, verbose_name=_("Last Used")
    )
    rejection_reason = models.TextField(
        blank=True, null=True, verbose_name=_("Rejection Reason")
    )

    class Meta:
        ordering = ["-is_default", "-added_at"]
        verbose_name = _("Bank Card")
        verbose_name_plural = _("Bank Cards")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "is_default"],
                condition=models.Q(is_default=True),
                name="unique_default_card_per_user",
            )
        ]

    def __str__(self):
        return f"{self.user}'s card - {self.card_number[-4:]}"

    def clean(self):
        super().clean()
        if self.is_default and self.status != BankCardStatus.VERIFIED:
            raise ValidationError(
                _("Only verified cards can be set as default.")
            )

    def save(self, *args, **kwargs):
        if self.is_default:
            # Unset is_default on all other cards for this user
            BankCard.objects.filter(user=self.user, is_default=True).exclude(
                pk=self.pk
            ).update(is_default=False)
        if not self._state.adding:
            original = BankCard.objects.get(pk=self.pk)
            if (
                self.card_number != original.card_number
                and original.status == BankCardStatus.REJECTED
            ):
                self.status = BankCardStatus.PENDING
                self.bank = None
                self.card_holder_name = ""
                self.is_default = False
                self.sheba = ""
        self.full_clean()
        super().save(*args, **kwargs)
