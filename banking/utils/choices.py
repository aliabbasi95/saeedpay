"""
Defines choices for the banking app.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class BankCardStatus(models.TextChoices):
    """
    Represents the status of a bank card.
    """

    VERIFIED = "verified", _("تایید شده")
    REJECTED = "rejected", _("رد شده")
    PENDING = "pending", _("در حال بررسی")
