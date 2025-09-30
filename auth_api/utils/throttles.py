# auth_api/utils/throttles.py

from rest_framework.throttling import SimpleRateThrottle
import re


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D+", "", phone or "")
    if digits.startswith("0098"):
        digits = "0" + digits[4:]
    elif digits.startswith("98"):
        digits = "0" + digits[2:]
    return digits


class OTPPhoneRateThrottle(SimpleRateThrottle):
    scope = "otp-by-phone"

    def get_cache_key(self, request, view):
        phone = request.data.get("phone_number") or request.query_params.get(
            "phone_number"
        )
        phone = normalize_phone(phone)
        if not phone:
            return None
        return self.cache_format % {"scope": self.scope, "ident": phone}
