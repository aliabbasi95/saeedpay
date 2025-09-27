# auth_api/tests/public/v1/views/test_register_merchant.py

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from auth_api.models import PhoneOTP
from merchants.models import Merchant
from profiles.models import Profile

REGISTER_MERCHANT_URL = "/saeedpay/api/auth/public/v1/register/merchant/"


@pytest.mark.django_db
class TestRegisterMerchantView:

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
        code = self.create_otp("09121110000")
        payload = {
            "phone_number": "09121110000",
            "code": code,
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        res = self.client.post(REGISTER_MERCHANT_URL, payload)
        assert res.status_code == status.HTTP_201_CREATED
        assert "access" in res.data
        assert "sp_refresh" in res.cookies
        assert res.data["phone_number"] == "09121110000"
        assert "merchant" in res.data["roles"]
        assert Merchant.objects.filter(user__username="09121110000").exists()

    def test_already_registered_merchant(self):
        user = get_user_model().objects.create(username="09121112222")
        Profile.objects.create(user=user, phone_number="09121112222")
        Merchant.objects.create(user=user)
        code = self.create_otp("09121112222")

        payload = {
            "phone_number": "09121112222",
            "code": code,
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        res = self.client.post(REGISTER_MERCHANT_URL, payload)
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "این شماره تلفن قبلاً به عنوان فروشنده ثبت شده است." in str(
            res.data
        )

    def test_password_mismatch(self):
        code = self.create_otp("09121113333")
        payload = {
            "phone_number": "09121113333",
            "code": code,
            "password": "StrongPass123!",
            "confirm_password": "WrongConfirm"
        }
        res = self.client.post(REGISTER_MERCHANT_URL, payload)
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "confirm_password" in str(res.data)

    def test_weak_password(self):
        code = self.create_otp("09121114444")
        payload = {
            "phone_number": "09121114444",
            "code": code,
            "password": "weak",
            "confirm_password": "weak"
        }
        res = self.client.post(REGISTER_MERCHANT_URL, payload)
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in str(res.data)

    def test_invalid_otp(self):
        self.create_otp("09121115555")
        payload = {
            "phone_number": "09121115555",
            "code": "wrong",
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        res = self.client.post(REGISTER_MERCHANT_URL, payload)
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "code" in str(res.data)

    def test_otp_missing(self):
        payload = {
            "phone_number": "09121116666",
            "code": "1234",
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        res = self.client.post(REGISTER_MERCHANT_URL, payload)
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "code" in str(res.data)

    def test_existing_user_without_merchant(self):
        user = get_user_model().objects.create(username="09121117777")
        code = self.create_otp("09121117777")
        payload = {
            "phone_number": "09121117777",
            "code": code,
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        res = self.client.post(REGISTER_MERCHANT_URL, payload)
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data["user_id"] == user.id
        assert Merchant.objects.filter(user=user).exists()

    def test_invalid_phone_number_format(self):
        code = self.create_otp("09121118888")
        payload = {
            "phone_number": "abc123",
            "code": code,
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        res = self.client.post(REGISTER_MERCHANT_URL, payload)
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "phone_number" in str(res.data)

    def test_missing_required_fields(self):
        res = self.client.post(REGISTER_MERCHANT_URL, {})
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "phone_number" in res.data
        assert "code" in res.data
        assert "password" in res.data
        assert "confirm_password" in res.data

    def test_otp_belongs_to_different_user(self):
        # user A gets otp
        code = self.create_otp("09120009999")

        # user B tries to register with that OTP
        payload = {
            "phone_number": "09120008888",
            "code": code,
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        res = self.client.post(REGISTER_MERCHANT_URL, payload)
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "کد تایید یافت نشد یا منقضی شده است." in str(res.data)

    def test_phone_number_with_spaces(self):
        code = self.create_otp("09121119999")
        payload = {
            "phone_number": " 09121119999 ",
            "code": code,
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        res = self.client.post(REGISTER_MERCHANT_URL, payload)
        assert res.status_code == status.HTTP_201_CREATED
        assert "merchant" in res.data["roles"]

    def test_profile_phone_number_updated_if_different(self):
        user = get_user_model().objects.create(username="09121112233")
        Profile.objects.create(user=user, phone_number="OLD_NUMBER")
        code = self.create_otp("09121112233")
        payload = {
            "phone_number": "09121112233",
            "code": code,
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        res = self.client.post(REGISTER_MERCHANT_URL, payload)
        profile = Profile.objects.get(user=user)
        assert profile.phone_number == "09121112233"
