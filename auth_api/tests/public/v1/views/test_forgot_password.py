# auth_api/tests/public/v1/views/test_forgot_password.py
import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from auth_api.models import PhoneOTP
from auth_api.utils.throttles import OTPPhoneRateThrottle

FORGOT_PASSWORD_URL = "/saeedpay/api/auth/public/v1/send-otp/"


@pytest.mark.django_db
class TestForgotPasswordView(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create(
            username="09123456789",
        )
        self.user.set_password("old_password")
        self.user.save()

    def test_successful_otp_request_for_existing_user(self):
        """
        Ensure an OTP is sent successfully for a registered user.
        """
        payload = {"phone_number": "09123456789"}
        response = self.client.post(FORGOT_PASSWORD_URL, payload)
        assert response.status_code == status.HTTP_200_OK
        assert "کد تأیید با موفقیت ارسال شد." in response.data["detail"]
        assert PhoneOTP.objects.filter(phone_number="09123456789").exists()

    def test_otp_request_for_non_existent_user(self):
        """
        Ensure the endpoint responds successfully even for non-existent users
        to prevent user enumeration.
        """
        payload = {"phone_number": "09120000000"}
        response = self.client.post(FORGOT_PASSWORD_URL, payload)

        assert response.status_code == status.HTTP_200_OK
        assert "کد تأیید با موفقیت ارسال شد." in response.data["detail"]
        # It should create an OTP object anyway to avoid timing attacks
        assert PhoneOTP.objects.filter(phone_number="09120000000").exists()

    def test_rate_limiting_on_otp_requests(self):
        """
        Ensure requests are rate-limited to prevent abuse.
        """
        # Manually set the rate for OTPPhoneRateThrottle for testing
        OTPPhoneRateThrottle.rate = "1/minute"
        payload = {"phone_number": "09121112222"}

        # First request should succeed
        response1 = self.client.post(FORGOT_PASSWORD_URL, payload)
        assert response1.status_code == status.HTTP_200_OK

        # Second request immediately after should be throttled
        response2 = self.client.post(FORGOT_PASSWORD_URL, payload)
        assert response2.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_invalid_phone_number_format(self):
        """
        Ensure an error is returned for an invalid phone number format.
        """
        payload = {"phone_number": "invalid-number"}
        response = self.client.post(FORGOT_PASSWORD_URL, payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "phone_number" in response.data

    def test_missing_phone_number_field(self):
        """
        Ensure an error is returned if the phone_number field is missing.
        """
        response = self.client.post(FORGOT_PASSWORD_URL, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "phone_number" in response.data

    def test_requesting_otp_when_one_is_already_active(self):
        """
        Ensure an error is returned if an active OTP already exists for the number.
        """
        phone_number = "09128889999"
        otp_instance = PhoneOTP.objects.create(phone_number=phone_number)
        otp_instance.send()  # This makes the OTP "alive"

        payload = {"phone_number": phone_number}
        response = self.client.post(FORGOT_PASSWORD_URL, payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "کد تایید شما ارسال شده است." in str(response.data) 