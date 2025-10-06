# auth_api/tests/public/v1/serializers/test_register_merchant.py

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from auth_api.api.public.v1.serializers import RegisterMerchantSerializer
from auth_api.models import PhoneOTP
from merchants.models import Merchant


@pytest.mark.django_db
class TestRegisterMerchantSerializer:

    def create_otp(self, phone_number):
        otp = PhoneOTP.objects.create(phone_number=phone_number)
        code = otp.generate()
        otp.last_send_date = timezone.localtime()
        otp.save()
        return code

    def test_successful_registration_new_user(self):
        code = self.create_otp("09123456789")
        serializer = RegisterMerchantSerializer(
            data={
                "phone_number": "09123456789",
                "code": code,
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()
        assert Merchant.objects.filter(user=user).exists()
        assert user.username == "09123456789"

    def test_passwords_do_not_match(self):
        self.create_otp("09121111111")
        serializer = RegisterMerchantSerializer(
            data={
                "phone_number": "09121111111",
                "code": "1111",
                "password": "TestPass123!",
                "confirm_password": "WrongConfirm!"
            }
        )
        with pytest.raises(ValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        assert "confirm_password" in str(exc.value)

    def test_weak_password(self):
        self.create_otp("09122222222")
        serializer = RegisterMerchantSerializer(
            data={
                "phone_number": "09122222222",
                "code": "2222",
                "password": "weak",
                "confirm_password": "weak"
            }
        )
        assert not serializer.is_valid()
        assert "password" in serializer.errors

    def test_missing_otp(self):
        serializer = RegisterMerchantSerializer(
            data={
                "phone_number": "09123334444",
                "code": "9999",
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )
        with pytest.raises(ValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        assert "code" in str(exc.value)

    def test_invalid_otp_code(self):
        self.create_otp("09124445555")
        serializer = RegisterMerchantSerializer(
            data={
                "phone_number": "09124445555",
                "code": "wrong",
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )
        with pytest.raises(ValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        assert "code" in str(exc.value)

    def test_already_registered_merchant(self):
        user = get_user_model().objects.create(username="09129998888")
        Merchant.objects.create(user=user)
        self.create_otp("09129998888")
        serializer = RegisterMerchantSerializer(
            data={
                "phone_number": "09129998888",
                "code": "9999",
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )
        with pytest.raises(ValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        assert "این شماره تلفن قبلاً به عنوان فروشنده ثبت شده است." in str(
            exc.value
        )

    def test_existing_user_without_merchant(self):
        user = get_user_model().objects.create(username="09126667777")
        code = self.create_otp("09126667777")
        serializer = RegisterMerchantSerializer(
            data={
                "phone_number": "09126667777",
                "code": code,
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )
        assert serializer.is_valid(), serializer.errors
        created_user = serializer.save()
        assert created_user.id == user.id
        assert Merchant.objects.filter(user=created_user).exists()

    def test_representation(self):
        code = self.create_otp("09127779999")
        serializer = RegisterMerchantSerializer(
            data={
                "phone_number": "09127779999",
                "code": code,
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()
        data = serializer.to_representation(user)
        assert data["phone_number"] == "09127779999"
        assert "merchant" in str(data["roles"])
