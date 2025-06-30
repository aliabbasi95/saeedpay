# auth_api/api/public/v1/serializers/register.py
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from auth_api.models import PhoneOTP
from auth_api.tokens import CustomRefreshToken
from customers.models import Customer
from lib.erp_base.serializers.persian_error_message import \
    PersianValidationErrorMessages
from lib.erp_base.validators.unique_across_models import \
    UniqueAcrossModelsValidator


class RegisterCustomerSerializer(
    PersianValidationErrorMessages, serializers.Serializer
):
    phone_number = serializers.CharField(
        max_length=11,
        validators=[
            UniqueAcrossModelsValidator(
                model_field_pairs=[
                    (get_user_model(), 'username'),
                    (Customer, 'phone_number'),
                ],
                message="این شماره تلفن قبلاً ثبت شده است."
            )
        ]
    )
    code = serializers.CharField()
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_phone_number(self, phone_number):
        User = get_user_model()

        user_exists = User.objects.filter(username=phone_number).exists()
        customer_exists = Customer.objects.filter(
            phone_number=phone_number
        ).exists()

        if user_exists or customer_exists:
            raise serializers.ValidationError(
                "این شماره تلفن قبلاً ثبت شده است."
            )

        return phone_number

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

    def create(self, validated_data):
        phone_number = validated_data['phone_number']
        password = validated_data['password']
        User = get_user_model()

        with transaction.atomic():
            user = User.objects.create(username=phone_number)
            user.set_password(password)
            user.save()

            Customer.objects.create(user=user, phone_number=phone_number)

        self.user = user
        return user

    def to_representation(self, instance):
        refresh = CustomRefreshToken.for_user(instance)
        roles = []
        if hasattr(instance, "customer"):
            roles.append("customer")
        if hasattr(instance, "seller"):
            roles.append("seller")

        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user_id": instance.id,
            "phone_number": instance.username,
            "roles": roles,
            "first_name": getattr(
                instance.customer if 'customer' in roles else instance.seller,
                "first_name", ""
            ),
            "last_name": getattr(
                instance.customer if 'customer' in roles else instance.seller,
                "last_name", ""
            ),
        }
