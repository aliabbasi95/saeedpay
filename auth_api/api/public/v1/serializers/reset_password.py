# auth_api/api/public/v1/serializers/reset_password.py
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import RegexValidator
from rest_framework import serializers

from auth_api.models import PhoneOTP
from lib.erp_base.serializers.persian_error_message import PersianValidationErrorMessages


class ResetPasswordSerializer(PersianValidationErrorMessages, serializers.Serializer):
    phone_number = serializers.CharField(
        max_length=11,
        validators=[
            RegexValidator(
                regex=r'^09\d{9}$',
                message="شماره تلفن معتبر نیست."
            ),
        ]
    )
    code = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_new_password(self, password):
        try:
            password_validation.validate_password(password=password)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)
        return password

    def validate(self, data):
        # Validate password confirmation
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': 'رمز عبور جدید و تکرار آن یکسان نیستند.'}
            )

        phone_number = data.get("phone_number")
        
        # Check if user exists with this phone number
        User = get_user_model()
        if not User.objects.filter(username=phone_number).exists():
            raise serializers.ValidationError(
                {"phone_number": "کاربری با این شماره تلفن یافت نشد."}
            )
        
        # Validate OTP
        code = data.get("code")
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

        return data

    def save(self, **kwargs):
        phone_number = self.validated_data['phone_number']
        new_password = self.validated_data['new_password']

        User = get_user_model()
        user = User.objects.get(username=phone_number)
        user.set_password(new_password)
        user.save()
        
        return user 