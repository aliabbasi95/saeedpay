# customers/models/customer.py
from django.contrib.auth import get_user_model
from django.db import models

from lib.erp_base.validators import validate_national_id


class Customer(models.Model):
    user = models.OneToOneField(
        get_user_model(),
        null=True,
        blank=False,
        on_delete=models.SET_NULL,
        related_name='customer',
    )
    phone_number = models.CharField(
        max_length=11,
        unique=True
    )
    national_id = models.CharField(
        null=True,
        blank=False,
        max_length=255,
        verbose_name='شناسه/کدملی',
        validators=[validate_national_id],
    )
    def __str__(self):
        return self.phone_number
