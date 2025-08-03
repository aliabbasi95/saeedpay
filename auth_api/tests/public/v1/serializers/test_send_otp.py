# auth_api/tests/public/v1/serializers/test_send_otp.py
import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from auth_api.api.public.v1.serializers import SendOTPSerializer
from auth_api.models import PhoneOTP


@pytest.mark.django_db
class TestSendOTPSerializer:

    def test_otp_created_if_not_exists(self):
        serializer = SendOTPSerializer(data={"phone_number": "09120000000"})
        assert serializer.is_valid(), serializer.errors
        serializer.save()

        otp = PhoneOTP.objects.filter(phone_number="09120000000").first()
        assert otp is not None
        assert otp.last_send_date is not None

    def test_existing_expired_otp_resends(self):
        otp = PhoneOTP.objects.create(phone_number="09121111111")
        otp.last_send_date = timezone.now() - timezone.timedelta(seconds=1000)
        otp.save()

        serializer = SendOTPSerializer(data={"phone_number": "09121111111"})
        assert serializer.is_valid()
        serializer.save()

        otp.refresh_from_db()
        assert otp.last_send_date is not None

    def test_existing_alive_otp_blocked(self):
        otp = PhoneOTP.objects.create(phone_number="09122222222")
        otp.last_send_date = timezone.localtime()
        otp.save()

        serializer = SendOTPSerializer(data={"phone_number": "09122222222"})
        with pytest.raises(ValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        assert "کد تایید شما ارسال شده است" in str(exc.value)

    def test_send_failure_raises_error(self, monkeypatch):
        def fake_send(self):
            return False

        monkeypatch.setattr(PhoneOTP, "send", fake_send)

        serializer = SendOTPSerializer(data={"phone_number": "09123334444"})
        assert serializer.is_valid()
        with pytest.raises(ValidationError) as exc:
            serializer.save()
        assert "ارسال کد با خطا مواجه شد" in str(exc.value)

    def test_missing_phone_number(self):
        serializer = SendOTPSerializer(data={})
        assert not serializer.is_valid()
        assert "phone_number" in serializer.errors

    def test_invalid_phone_number_format(self):
        serializer = SendOTPSerializer(data={"phone_number": "invalid!"})
        assert not serializer.is_valid()
        assert "phone_number" in serializer.errors
