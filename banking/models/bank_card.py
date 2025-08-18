# banking/models/bank_card.py

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from banking.utils.choices import BankCardStatus
from lib.erp_base.models import BaseModel
from .bank import Bank


class BankCard(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bank_cards",
        verbose_name=_("کاربر"),
    )
    bank = models.ForeignKey(
        Bank,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cards",
        verbose_name=_("بانک"),
    )
    card_number = models.CharField(
        max_length=16,
        db_index=True,
        verbose_name=_("شماره کارت"),
    )
    card_holder_name = models.CharField(
        max_length=70,
        blank=True,
        verbose_name=_("نام دارنده کارت"),
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name=_("کارت پیش‌فرض"),
    )
    status = models.CharField(
        max_length=20,
        choices=BankCardStatus.choices,
        default=BankCardStatus.PENDING,
        verbose_name=_("وضعیت"),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("فعال"),
    )
    sheba = models.CharField(
        max_length=26,
        blank=True,
        null=True,
        verbose_name=_("شماره شِبا"),
    )
    last_used = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("آخرین استفاده"),
    )
    rejection_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("دلیل رد"),
    )

    @property
    def last4(self):
        return self.card_number[-4:] if self.card_number else ""

    def clean(self):
        super().clean()
        errors = {}
        if self.card_number:
            from banking.services import bank_card_service
            if not bank_card_service.is_luhn_valid(self.card_number):
                errors["card_number"] = _("شماره کارت نامعتبر است.")
        if self.is_default and self.status != BankCardStatus.VERIFIED:
            errors["is_default"] = _(
                "فقط کارت‌های تأیید‌شده می‌توانند پیش‌فرض شوند."
            )
        if self.card_number:
            exists_other_verified = type(self).objects.filter(
                card_number=self.card_number, status=BankCardStatus.VERIFIED
            ).exclude(user=self.user).exists()
            if exists_other_verified:
                errors["card_number"] = _(
                    "این شماره کارت قبلاً توسط کاربر دیگری تأیید شده است."
                )
        raise ValidationError(errors)

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

    def __str__(self):
        return f"{self.user}'s card - {self.card_number[-4:]}"

    class Meta:
        ordering = ["-is_default", "-created_at"]
        verbose_name = _("کارت بانکی")
        verbose_name_plural = _("کارت‌های بانکی")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "is_default"],
                condition=models.Q(is_default=True),
                name="unique_default_card_per_user",
                violation_error_message=_(
                    "فقط یک کارت می‌تواند پیش‌فرض باشد."
                ),
            ),
            models.UniqueConstraint(
                fields=["user", "card_number"],
                name="unique_card_per_user",
                violation_error_message=_(
                    "شما قبلاً این کارت را ثبت کرده‌اید."
                ),
            ),
            models.UniqueConstraint(
                fields=["card_number"],
                condition=models.Q(status="verified"),
                name="unique_verified_card_number",
                violation_error_message=_(
                    "این شماره کارت قبلاً به‌صورت تأیید‌شده ثبت شده است."
                ),
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "is_active"], name="bankcard_user_active_idx"
            ),
            models.Index(
                fields=["-is_default", "-created_at"],
                name="bankcard_default_added_idx"
            ),
        ]
