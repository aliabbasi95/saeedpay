# auth_api/models/otp.py

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models.otp import OTP
from lib.erp_base.tasks import send_sms


class PhoneOTP(OTP):
    phone_number = models.CharField(
        max_length=15,
        verbose_name=_("شماره تلفن"),
    )

    def send(self):
        if not self.is_alive():
            code = self.generate()
            if settings.CAS_DEBUG:
                print(code)
            else:
                send_sms.apply_async(
                    (
                        self.phone_number,
                        f"Verification code: {code}"
                    )
                )
            self.last_send_date = timezone.localtime(timezone.now())
            self.save(update_fields=["last_send_date"])
        return True
