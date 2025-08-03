# auth_api/tests/public/v1/views/test_send_otp.py
import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from auth_api.models import PhoneOTP

SEND_OTP_URL = "/saeedpay/api/auth/public/v1/send-otp/"


@pytest.mark.django_db
class TestSendOTPView:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def test_send_otp_successfully(self):
        response = self.client.post(
            SEND_OTP_URL, {"phone_number": "09124445555"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["detail"] == "کد تأیید با موفقیت ارسال شد."
        assert PhoneOTP.objects.filter(phone_number="09124445555").exists()

    def test_block_alive_otp(self):
        otp = PhoneOTP.objects.create(phone_number="09125556666")
        otp.last_send_date = timezone.localtime()
        otp.save()

        response = self.client.post(
            SEND_OTP_URL, {"phone_number": "09125556666"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "کد تایید شما ارسال شده است" in str(response.data)

    def test_resend_expired_otp(self):
        otp = PhoneOTP.objects.create(phone_number="09126667777")
        otp.last_send_date = timezone.now() - timezone.timedelta(seconds=1000)
        otp.save()

        response = self.client.post(
            SEND_OTP_URL, {"phone_number": "09126667777"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["detail"] == "کد تأیید با موفقیت ارسال شد."

    def test_send_failure_simulated(self, monkeypatch):
        def fake_send(self):
            return False

        monkeypatch.setattr(PhoneOTP, "send", fake_send)

        response = self.client.post(
            SEND_OTP_URL, {"phone_number": "09127778888"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "ارسال کد با خطا مواجه شد" in str(response.data)

    def test_missing_phone_number(self):
        response = self.client.post(SEND_OTP_URL, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "phone_number" in response.data

    def test_invalid_phone_number_format(self):
        response = self.client.post(SEND_OTP_URL, {"phone_number": "abc123"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "phone_number" in response.data
