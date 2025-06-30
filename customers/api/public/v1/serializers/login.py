# customers/api/public/v1/serializers/login.py
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from lib.erp_base.serializers.persian_error_message import \
    PersianValidationErrorMessages


class LoginSerializer(PersianValidationErrorMessages, serializers.Serializer):
    phone_number = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        phone = data.get("phone_number")
        password = data.get("password")
        User = get_user_model()

        try:
            user = User.objects.get(username=phone)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                _("شماره تلفن یا رمز عبور اشتباه است.")
            )

        if not user.check_password(password):
            raise serializers.ValidationError(
                _("شماره تلفن یا رمز عبور اشتباه است.")
            )

        if not user.is_active:
            raise serializers.ValidationError(
                _("حساب کاربری شما غیرفعال است.")
            )

        self.user = user
        return data

    def create(self, validated_data):
        return self.user

    def to_representation(self, instance):
        return {
            **instance.tokens(),
            "user_id": instance.id,
            "phone_number": instance.username,
            "first_name": getattr(instance.customer, "first_name", ""),
            "last_name": getattr(instance.customer, "last_name", ""),
        }
