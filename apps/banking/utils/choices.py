# banking/utils/choices.py

from django.db import models
from django.utils.translation import gettext_lazy as _


class BankCardStatus(models.TextChoices):
    VERIFIED = "verified", _("تایید شده")
    REJECTED = "rejected", _("رد شده")
    PENDING = "pending", _("در حال بررسی")
