# customers/models/otp.py
import pyotp

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from lib.erp_base.tasks import send_sms
from lib.erp_base.models.base import BaseModel

from ..utils.consts import LIFE_DURATION


class PhoneOTP(BaseModel):
    phone_number = models.CharField(
        max_length=15,
        verbose_name=_("شماره تلفن"),
    )
    secret = models.CharField(
        max_length=32,
        unique=True,
        default=pyotp.random_base32,
        verbose_name=_("کلید محرمانه"),
    )
    last_send_date = models.DateTimeField(
        null=True,
        verbose_name=_("تاریخ و زمان آخرین ارسال")
    )

    def generate(self, new_secret: bool = False):
        if new_secret:
            self.secret = pyotp.random_base32()
            self.save()

        totp = pyotp.TOTP(self.secret, interval=LIFE_DURATION)
        return totp.now()

    def is_alive(self):
        if not self.last_send_date:
            return False
        elapsed_time = (timezone.localtime(timezone.now()) - timezone.localtime(self.last_send_date)).total_seconds()
        return elapsed_time < LIFE_DURATION

    def verify(self, code):
        totp = pyotp.TOTP(self.secret, interval=LIFE_DURATION)
        if totp.verify(code):
            self.delete()
            return True
        return False

    def send(self):
        if not self.is_alive():
            code = self.generate()
            send_sms.apply_async((
                self.phone_number,
                f"Verification code: {code}"
            ))
            self.last_send_date = timezone.localtime(timezone.now())
            self.save()
        return True
