# auth_api/api/public/v1/serializers/otp.py
from rest_framework import serializers

from auth_api.models import PhoneOTP


class SendOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        max_length=11,
    )

    def validate(self, data):
        phone_number = data.get("phone_number")
        otp = PhoneOTP.objects.filter(phone_number=phone_number).first()
        if otp and otp.is_alive():
            raise serializers.ValidationError(
                {"phone_number": ["کد تایید شما ارسال شده است."]}
            )
        return data

    def create(self, validated_data):
        phone_number = validated_data["phone_number"]
        otp_instance, _ = PhoneOTP.objects.get_or_create(
            phone_number=phone_number
        )
        if otp_instance.send():
            return validated_data
        raise serializers.ValidationError(
            {"phone_number": ["ارسال کد با خطا مواجه شد."]}
        )
