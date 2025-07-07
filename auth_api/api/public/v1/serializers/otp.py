# auth_api/api/public/v1/serializers/otp.py
from django.core.validators import RegexValidator
from rest_framework import serializers

from auth_api.models import PhoneOTP


class SendOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        max_length=11,
        validators=[
            RegexValidator(
                regex=r'^09\d{9}$',
                message="شماره تلفن معتبر نیست."
            ),
        ]
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
        print(1000)
        raise serializers.ValidationError(
            {"phone_number": ["ارسال کد با خطا مواجه شد."]}
        )
