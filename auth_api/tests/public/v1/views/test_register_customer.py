# auth_api/tests/public/v1/serializers/test_register_customer.py

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from auth_api.models import PhoneOTP
from customers.models import Customer
from profiles.models import Profile

REGISTER_URL = "/saeedpay/api/auth/public/v1/register/customer/"


@pytest.mark.django_db
class TestRegisterCustomerView:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def create_otp(self, phone_number):
        otp = PhoneOTP.objects.create(phone_number=phone_number)
        code = otp.generate()
        otp.last_send_date = timezone.localtime()
        otp.save()
        return code

    def test_successful_registration(self):
        code = self.create_otp("09123456789")
        payload = {
            "phone_number": "09123456789",
            "code": code,
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        response = self.client.post(REGISTER_URL, payload)
        assert response.status_code == status.HTTP_201_CREATED
        assert "access" in response.data
        assert "sp_refresh" in response.cookies
        assert "user_id" in response.data
        assert response.data["phone_number"] == "09123456789"
        assert "customer" in response.data["roles"]
        assert Customer.objects.filter(user__username="09123456789").exists()

    def test_registration_existing_user_without_customer(self):
        user = get_user_model().objects.create(username="09120001111")
        code = self.create_otp("09120001111")

        payload = {
            "phone_number": "09120001111",
            "code": code,
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        response = self.client.post(REGISTER_URL, payload)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["user_id"] == user.id
        assert Customer.objects.filter(user=user).exists()

    def test_otp_invalid(self):
        self.create_otp("09120002222")
        payload = {
            "phone_number": "09120002222",
            "code": "wrongcode",
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        response = self.client.post(REGISTER_URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "code" in str(response.data)

    def test_otp_missing(self):
        payload = {
            "phone_number": "09120003333",
            "code": "1234",
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        response = self.client.post(REGISTER_URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "code" in str(response.data)

    def test_already_registered_customer(self):
        user = get_user_model().objects.create(username="09120004444")
        Profile.objects.create(user=user, phone_number="09120004444")
        Customer.objects.create(user=user)
        code = self.create_otp("09120004444")

        payload = {
            "phone_number": "09120004444",
            "code": code,
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        response = self.client.post(REGISTER_URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "این شماره تلفن قبلاً به عنوان مشتری ثبت شده است." in str(
            response.data
        )

    def test_password_mismatch(self):
        code = self.create_otp("09120005555")
        payload = {
            "phone_number": "09120005555",
            "code": code,
            "password": "StrongPass123!",
            "confirm_password": "WrongConfirm"
        }
        response = self.client.post(REGISTER_URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "confirm_password" in str(response.data)

    def test_weak_password(self):
        code = self.create_otp("09120006666")
        payload = {
            "phone_number": "09120006666",
            "code": code,
            "password": "weak",
            "confirm_password": "weak"
        }
        response = self.client.post(REGISTER_URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in str(response.data)

    def test_invalid_phone_number_format(self):
        code = self.create_otp("09120007777")
        payload = {
            "phone_number": "abcde12345",
            "code": code,
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        response = self.client.post(REGISTER_URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "phone_number" in str(response.data)

    def test_missing_required_fields(self):
        response = self.client.post(REGISTER_URL, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "phone_number" in response.data
        assert "code" in response.data
        assert "password" in response.data
        assert "confirm_password" in response.data

    def test_otp_deleted_after_use(self):
        phone = "09120008888"
        code = self.create_otp(phone)

        # First use (success)
        response1 = self.client.post(
            REGISTER_URL, {
                "phone_number": phone,
                "code": code,
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )
        assert response1.status_code == status.HTTP_201_CREATED

        # Remove customer to bypass UniqueAcrossModelsValidator
        get_user_model().objects.filter(username=phone).delete()

        # Second attempt (should now fail due to OTP being deleted)
        response2 = self.client.post(
            REGISTER_URL, {
                "phone_number": phone,
                "code": code,
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )

        assert response2.status_code == status.HTTP_400_BAD_REQUEST
        assert "کد تایید یافت نشد" in str(response2.data)

    def test_phone_number_with_spaces(self):
        code = self.create_otp("09123334444")
        payload = {
            "phone_number": " 09123334444 ",  # spaces
            "code": code,
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        response = self.client.post(REGISTER_URL, payload)
        assert response.status_code == status.HTTP_201_CREATED
        assert "customer" in response.data["roles"]

    def test_profile_phone_number_updated_if_different(self):
        user = get_user_model().objects.create(username="09124445555")
        Profile.objects.create(user=user, phone_number="OLD")
        code = self.create_otp("09124445555")
        payload = {
            "phone_number": "09124445555",
            "code": code,
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        res = self.client.post(REGISTER_URL, payload)
        profile = Profile.objects.get(user=user)
        assert profile.phone_number == "09124445555"
