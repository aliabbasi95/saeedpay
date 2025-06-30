# customers/models/customer.py
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
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
        blank=False,
        unique=True
    )
    national_id = models.CharField(
        null=True,
        blank=True,
        max_length=255,
        verbose_name='شناسه/کدملی',
        validators=[validate_national_id],
    )
    first_name = models.CharField(
        blank=True,
        max_length=255,
        verbose_name='نام',
    )
    last_name = models.CharField(
        blank=True,
        max_length=255,
        verbose_name='نام خانوادگی',
    )
    birth_date = models.CharField(
        max_length=10,
        null=True,
        blank=False,
        verbose_name='تاریخ تولد',
        validators=[RegexValidator(
            r'\d\d\d\d\/\d\d\/\d\d', 'format : YYYY/MM/DD'
        )],
        help_text='format: YYYY/MM/DD'
    )

    def __str__(self):
        return self.phone_number
