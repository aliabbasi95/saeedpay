# auth_api/tests/public/v1/views/test_reset_password.py
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from auth_api.models import PhoneOTP

RESET_PASSWORD_URL = "/saeedpay/api/auth/public/v1/reset-password/"


@pytest.mark.django_db
class TestResetPasswordView(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create(
            username="09123456789"
        )
        self.user.set_password("old_password")
        self.user.save()
        self.phone_number = "09123456789"

    def create_valid_otp(self):
        otp = PhoneOTP.objects.create(phone_number=self.phone_number)
        code = otp.generate()
        otp.last_send_date = timezone.localtime()
        otp.save()
        return code

    def test_successful_password_reset(self):
        """
        Ensure a password can be successfully reset with a valid OTP code.
        """
        code = self.create_valid_otp()
        payload = {
            "phone_number": self.phone_number,
            "code": code,
            "new_password": "NewStrongPassword123!",
            "confirm_password": "NewStrongPassword123!",
        }
        response = self.client.post(RESET_PASSWORD_URL, payload)
        assert response.status_code == status.HTTP_200_OK
        assert "رمز عبور با موفقیت بازنشانی شد." in response.data["detail"]

        # Verify the password was actually changed
        self.user.refresh_from_db()
        assert self.user.check_password("NewStrongPassword123!")
        assert not self.user.check_password("old_password")

    def test_password_reset_with_invalid_code(self):
        """
        Ensure password reset fails with an invalid OTP code.
        """
        self.create_valid_otp()  # A valid OTP exists but we use a wrong one
        payload = {
            "phone_number": self.phone_number,
            "code": "invalidcode",
            "new_password": "NewStrongPassword123!",
            "confirm_password": "NewStrongPassword123!",
        }
        response = self.client.post(RESET_PASSWORD_URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "کد تایید اشتباه یا منقضی شده است." in str(response.data)

    def test_password_reset_with_missing_otp(self):
        """
        Ensure password reset fails if no OTP has been sent for the number.
        """
        payload = {
            "phone_number": self.phone_number,
            "code": "12345",
            "new_password": "NewStrongPassword123!",
            "confirm_password": "NewStrongPassword123!",
        }
        response = self.client.post(RESET_PASSWORD_URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "کد تایید یافت نشد یا منقضی شده است." in str(response.data)

    def test_password_reset_for_non_existent_user(self):
        """
        Ensure password reset fails for a phone number not linked to any user.
        """
        code = self.create_valid_otp()  # Create OTP for a non-user number
        payload = {
            "phone_number": "09120000000",
            "code": code,
            "new_password": "NewStrongPassword123!",
            "confirm_password": "NewStrongPassword123!",
        }
        response = self.client.post(RESET_PASSWORD_URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "کاربری با این شماره تلفن یافت نشد." in str(response.data)

    def test_password_mismatch(self):
        """
        Ensure an error is returned if the new password and confirmation don't match.
        """
        code = self.create_valid_otp()
        payload = {
            "phone_number": self.phone_number,
            "code": code,
            "new_password": "NewStrongPassword123!",
            "confirm_password": "MismatchPassword",
        }
        response = self.client.post(RESET_PASSWORD_URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "رمز عبور جدید و تکرار آن یکسان نیستند." in str(response.data)

    def test_weak_password(self):
        """
        Ensure a weak password is rejected.
        """
        code = self.create_valid_otp()
        payload = {
            "phone_number": self.phone_number,
            "code": code,
            "new_password": "weak",
            "confirm_password": "weak",
        }
        response = self.client.post(RESET_PASSWORD_URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in str(response.data)

    def test_missing_required_fields(self):
        """
        Ensure errors are returned for all missing required fields.
        """
        response = self.client.post(RESET_PASSWORD_URL, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "phone_number" in response.data
        assert "code" in response.data
        assert "new_password" in response.data
        assert "confirm_password" in response.data 