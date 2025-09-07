# contact/models/contact.py

from django.core.validators import RegexValidator
from django.db import models

from lib.erp_base.models.base import BaseModel

phone_validator = RegexValidator(
    regex=r'^\+?[0-9\s\-\(\)\.]{7,20}$',
    message="Please enter a valid phone number."
)


class Contact(BaseModel):
    """
    Simple contact message model.
    NOTE:
    - Keep fields minimal and stable to avoid breaking API.
    - Basic phone format validator added (international-friendly).
    """
    name = models.CharField(max_length=255, verbose_name="نام و نام خانوادگی")
    email = models.EmailField(verbose_name="ایمیل")
    phone = models.CharField(
        max_length=20, validators=[phone_validator], verbose_name="شماره تماس"
    )
    message = models.TextField(verbose_name="پیام شما")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """
        Normalize basic text fields before saving.
        """
        if self.name:
            self.name = self.name.strip()
        if self.email:
            self.email = self.email.strip().lower()
        if self.phone:
            self.phone = self.phone.strip()
        if self.message:
            self.message = self.message.strip()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.email}"

    class Meta:
        verbose_name = "پیام تماس"
        verbose_name_plural = "پیام‌های تماس"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"], name="contact_created_idx"),
            models.Index(fields=["email"], name="contact_email_idx"),
        ]
