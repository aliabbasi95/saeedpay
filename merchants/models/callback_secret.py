# merchants/models/callback_secret.py
import secrets

from django.db import models
from django.utils import timezone


class MerchantCallbackSecret(models.Model):
    merchant = models.OneToOneField(
        "merchants.Merchant",
        on_delete=models.CASCADE,
        related_name="callback_secret",
        verbose_name="فروشنده"
    )
    secret = models.CharField(
        max_length=128,
        unique=True,
        verbose_name="کلید مخفی Callback"
    )
    last_regenerated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="آخرین زمان تولید مجدد"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال"
    )

    @classmethod
    def generate_secret(cls):
        return secrets.token_urlsafe(48)

    def regenerate(self):
        self.secret = self.generate_secret()
        self.last_regenerated_at = timezone.now()
        self.is_active = True
        self.save()
        return self.secret

    def __str__(self):
        return f"Callback Secret for Merchant {self.merchant.profile.phone_number}"

    class Meta:
        verbose_name = "کلید Callback فروشنده"
        verbose_name_plural = "کلیدهای Callback فروشندگان"
