# apps/auth_api/api/public/v1/serializers/otp.py
import re

from django.core.validators import RegexValidator
from rest_framework import serializers

from lib.erp_base.otp.services import OtpService

PURPOSE_MAP = {1: "SIGNUP", 2: "RESET_PASSWORD"}

class SendOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        max_length=11,
        validators=[
            RegexValidator(regex=r"^09\d{9}$", message="شماره تلفن معتبر نیست."),
        ],
    )
    
    purpose = serializers.ChoiceField(choices=[1, 2], default=1)


    def create(self, validated_data):
        request = self.context.get("request")
        phone_number = validated_data["phone_number"]
        purpose = PURPOSE_MAP.get(validated_data.get("purpose", 1), "SIGNUP")
        
        try:
            OtpService.issue(
                identity=phone_number,
                purpose=purpose,
                channel="sms",
                ip=request.META.get("REMOTE_ADDR") if request else None,
                user_agent=request.META.get("HTTP_USER_AGENT") if request else None,
            )
        except Exception as exc:            
            if str(exc) == "rate_limited":
                raise serializers.ValidationError(
                    "محدودیت ارسال کد. بعداً تلاش کنید", code="RATE_LIMITED"
                ) from exc
            raise serializers.ValidationError(
                "خطای ارسال پیامک", code="SMS_SEND_FAILED"
            ) from exc

        return {"detail": "کد OTP ارسال شد"}

