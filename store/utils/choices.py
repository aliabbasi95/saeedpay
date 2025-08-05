# store/utils/choices.py

from django.db import models
from django.utils.translation import gettext_lazy as _


class StoreUserRole(models.TextChoices):
    MANAGER = 'manager', _('مدیر فروشگاه')
    STAFF = 'staff', _('کارمند')
    ACCOUNTANT = 'accountant', _('حسابدار')


class StoreVerificationStatus(models.TextChoices):
    PENDING = "pending", _("در انتظار تایید")
    APPROVED = "approved", _("تایید شده")
    REJECTED = "rejected", _("رد شده")
