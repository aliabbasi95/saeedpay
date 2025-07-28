# profiles/models/profile.py
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from lib.erp_base.validators import validate_national_id


class Profile(BaseModel):
    user = models.OneToOneField(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="کاربر"
    )
    phone_number = models.CharField(
        max_length=11,
        unique=True
    )
    email = models.EmailField(
        blank=True,
        verbose_name="ایمیل",
    )
    national_id = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="کد ملی",
        validators=[validate_national_id],
    )
    first_name = models.CharField(
        blank=True,
        max_length=255,
        verbose_name="نام",
    )
    last_name = models.CharField(
        blank=True,
        max_length=255,
        verbose_name="نام خانوادگی",
    )
    birth_date = models.CharField(
        max_length=10,
        null=True,
        blank=False,
        verbose_name="تاریخ تولد",
        validators=[RegexValidator(
            r"\d\d\d\d\/\d\d\/\d\d", "format : YYYY/MM/DD"
        )],
        help_text="format: YYYY/MM/DD"
    )

    @property
    def full_name(self):
        full_name = "%s %s" % (self.first_name, self.last_name)
        return full_name.strip()

    def __str__(self):
        return f"پروفایل {self.user.username}"

    class Meta:
        verbose_name = _("پروفایل")
        verbose_name_plural = _("پروفایل‌ها")
        constraints = [
            models.UniqueConstraint(
                fields=['national_id'],
                name='unique_national_id_not_null',
                condition=models.Q(national_id__isnull=False)
            )
        ]
