# auth_api/api/public/v1/serializers/register.py

from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import RegexValidator
from django.db import transaction
from rest_framework import serializers

from auth_api.api.public.v1.serializers.mixins import (
    UserPublicPayloadMixin,
    OTPValidationMixin,
)
from customers.models import Customer
from lib.erp_base.serializers.persian_error_message import \
    PersianValidationErrorMessages
from profiles.models import Profile
from wallets.services import create_default_wallets_for_user
from wallets.utils.choices import OwnerType


class RegisterCustomerSerializer(
    PersianValidationErrorMessages,
    UserPublicPayloadMixin,
    OTPValidationMixin,
    serializers.Serializer
):
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
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_password(self, password):
        try:
            password_validation.validate_password(password=password)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)
        return password

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': 'رمز عبور و تکرار آن یکسان نیستند.'}
            )

        phone_number = data.get("phone_number")

        if Customer.objects.filter(
                user__username=phone_number
        ).exists():
            raise serializers.ValidationError(
                {
                    "phone_number": "این شماره تلفن قبلاً به عنوان مشتری ثبت شده است."
                }
            )

        self.validate_phone_otp(phone_number, data["code"])

        return data

    def create(self, validated_data):
        phone_number = validated_data['phone_number']
        password = validated_data['password']

        User = get_user_model()

        with transaction.atomic():
            user, _ = User.objects.get_or_create(username=phone_number)
            user.set_password(password)
            user.save()
            profile, _ = Profile.objects.get_or_create(
                user=user, defaults={"phone_number": phone_number}
            )
            if profile.phone_number != phone_number:
                profile.phone_number = phone_number
                profile.save()
            Customer.objects.create(
                user=user
            )
            create_default_wallets_for_user(
                user, owner_type=OwnerType.CUSTOMER
            )

        self.user = user
        return user

    def to_representation(self, instance):
        return self.build_user_public_payload(instance)
