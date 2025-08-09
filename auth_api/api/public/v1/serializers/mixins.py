# auth_api/api/public/v1/serializers/mixins.py

from rest_framework import serializers

from auth_api.models import PhoneOTP


class UserPublicPayloadMixin:

    @staticmethod
    def build_user_public_payload(user):
        roles = []
        if hasattr(user, "customer"):
            roles.append("customer")
        if hasattr(user, "merchant"):
            roles.append("merchant")
        profile = getattr(user, "profile", None)
        return {
            "user_id": user.id,
            "phone_number": getattr(profile, "phone_number", ""),
            "roles": roles,
            "first_name": getattr(profile, "first_name", ""),
            "last_name": getattr(profile, "last_name", ""),
        }


class OTPValidationMixin:
    def validate_phone_otp(self, phone_number: str, code: str):
        try:
            otp_instance = PhoneOTP.objects.get(phone_number=phone_number)
        except PhoneOTP.DoesNotExist:
            raise serializers.ValidationError(
                {"code": "کد تایید یافت نشد یا منقضی شده است."}
                )
        if not otp_instance.verify(code):
            raise serializers.ValidationError(
                {"code": "کد تایید اشتباه یا منقضی شده است."}
                )
