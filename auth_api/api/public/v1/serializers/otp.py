# auth_api/api/public/v1/serializers/otp.py
import re

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
        raise serializers.ValidationError(
            {"phone_number": ["ارسال کد با خطا مواجه شد."]}
        )


class SendUserOTPSerializer(serializers.Serializer):

    def validate(self, data):
        user = self.context["request"].user
        phone_number = user.profile.phone_number

        if not phone_number or not re.match(r'^09\d{9}$', phone_number):
            raise serializers.ValidationError(
                {"phone_number": ["شماره تلفن معتبر نیست."]}
            )

        otp = PhoneOTP.objects.filter(phone_number=phone_number).first()
        if otp and otp.is_alive():
            raise serializers.ValidationError(
                {"phone_number": ["کد تایید شما ارسال شده است."]}
            )
        return data

    def create(self, validated_data):
        user = self.context["request"].user
        phone_number = user.profile.phone_number

        otp_instance, _ = PhoneOTP.objects.get_or_create(
            phone_number=phone_number
        )
        if otp_instance.send():
            return {"phone_number": phone_number}
        raise serializers.ValidationError(
            {"phone_number": ["ارسال کد با خطا مواجه شد."]}
        )