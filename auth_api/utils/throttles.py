# auth_api/utils/throttles.py
from rest_framework.throttling import SimpleRateThrottle


class OTPPhoneRateThrottle(SimpleRateThrottle):
    scope = "otp_by_phone"
    rate = "3/minute"

    def get_cache_key(self, request, view):
        phone = request.data.get("phone_number")
        if not phone:
            return None
        return self.cache_format % {"scope": self.scope, "ident": phone}
