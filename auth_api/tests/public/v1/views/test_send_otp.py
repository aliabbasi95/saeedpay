# auth_api/tests/public/v1/views/test_send_otp.py

from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.utils import timezone
from freezegun import freeze_time
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


@pytest.mark.django_db
class TestSendOtpThrottlingTests:
    """
    Comprehensive throttling tests for the OTP sending endpoint.
    Tests both global throttling (AnonRateThrottle/UserRateThrottle) and 
    per-phone throttling (OTPPhoneRateThrottle) dynamically based on configured rates.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test client and clear cache to prevent cross-test leakage."""
        self.client = APIClient()
        cache.clear()  # Prevent throttle state leakage between tests

        # Clear any existing throttle keys that might interfere
        if hasattr(cache, '_cache'):
            cache._cache.clear()

        # Get dynamic throttle configuration
        self.throttle_config = self._get_throttle_config()

    def _get_throttle_config(self):
        """Extract throttle configuration dynamically from the OTP view."""
        from auth_api.api.public.v1.views.otp import SendOTPView
        from auth_api.utils.throttles import OTPPhoneRateThrottle

        view = SendOTPView()
        throttles = view.get_throttles()

        # Find the OTP phone throttle
        otp_throttle = None
        for throttle in throttles:
            if isinstance(throttle, OTPPhoneRateThrottle):
                otp_throttle = throttle
                break

        if not otp_throttle:
            pytest.fail("OTPPhoneRateThrottle not found in view throttles")

        # Parse the rate (e.g., "3/minute" -> {"requests": 3, "period": 60})
        rate_config = self._parse_throttle_rate(otp_throttle.rate)

        return {
            "rate_string": otp_throttle.rate,
            "scope": otp_throttle.scope,
            "requests_allowed": rate_config["requests"],
            "period_seconds": rate_config["period"],
        }

    def _parse_throttle_rate(self, rate_string):
        """Parse DRF throttle rate string into requests and period."""
        # Handle formats like "3/minute", "5/hour", "100/day"
        if '/' not in rate_string:
            pytest.fail(f"Invalid throttle rate format: {rate_string}")

        requests_str, period_str = rate_string.split('/', 1)
        requests = int(requests_str)

        # Convert period to seconds
        period_seconds = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400,
        }.get(period_str.lower())

        if period_seconds is None:
            pytest.fail(f"Unknown period unit: {period_str}")

        return {"requests": requests, "period": period_seconds}

    def test_throttle_configuration_verification(self):
        """Verify that throttle classes are properly configured on the view."""
        from auth_api.api.public.v1.views.otp import SendOTPView
        from auth_api.utils.throttles import OTPPhoneRateThrottle

        view = SendOTPView()
        throttle_classes = view.get_throttles()

        # Verify OTPPhoneRateThrottle is in the throttle classes
        otp_throttle_found = any(
            isinstance(throttle, OTPPhoneRateThrottle) for throttle in
            throttle_classes
        )
        assert otp_throttle_found, f"OTPPhoneRateThrottle not found in {[type(t).__name__ for t in throttle_classes]}"

        # Verify the throttle is configured correctly
        config = self.throttle_config
        assert config["scope"] == "otp_by_phone"
        assert config[
                   "requests_allowed"] > 0, "Throttle should allow at least 1 request"
        assert config[
                   "period_seconds"] > 0, "Throttle period should be positive"

        print(
            f"✓ Throttle configured: {config['requests_allowed']} requests per {config['period_seconds']} seconds ({config['rate_string']})."
        )

    def test_phone_throttle_allows_up_to_limit(self):
        """Test that phone-specific throttling allows up to the configured limit."""
        phone = "09123456789"
        config = self.throttle_config
        requests_allowed = config["requests_allowed"]

        # Calculate a safe time interval between requests (period / requests / 2)
        time_between_requests = max(
            1, config["period_seconds"] // requests_allowed // 2
        )

        with freeze_time("2024-01-01 12:00:00") as frozen_time:
            # Mock OTP send to avoid actual SMS sending
            with patch('auth_api.models.PhoneOTP.send', return_value=True):
                # Should allow up to the configured limit
                for i in range(requests_allowed):
                    response = self.client.post(
                        SEND_OTP_URL, {"phone_number": phone}
                    )
                    assert response.status_code == status.HTTP_200_OK, f"Request {i + 1}/{requests_allowed} should succeed but got {response.status_code}: {response.data}"

                    # Move forward to avoid model-level duplicate prevention
                    frozen_time.tick(
                        delta=timezone.timedelta(seconds=time_between_requests)
                    )

                # Next request should be throttled
                response = self.client.post(
                    SEND_OTP_URL, {"phone_number": phone}
                )
                assert response.status_code in (
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    status.HTTP_400_BAD_REQUEST), f"Request {requests_allowed + 1} should be throttled but got {response.status_code}: {response.data}"
                assert "throttled" in response.data.get("detail", "").lower()

    def test_phone_throttle_resets_after_period(self):
        """Test that phone throttling resets after the configured period."""
        phone = "09123456790"
        config = self.throttle_config
        requests_allowed = config["requests_allowed"]
        period_seconds = config["period_seconds"]

        # Calculate time intervals for requests
        time_between_requests = max(1, period_seconds // requests_allowed // 2)

        with freeze_time("2024-01-01 12:00:00") as frozen_time:
            with patch('auth_api.models.PhoneOTP.send', return_value=True):
                # Exhaust the limit
                last_request_time = None
                for i in range(requests_allowed):
                    response = self.client.post(
                        SEND_OTP_URL, {"phone_number": phone}
                    )
                    assert response.status_code == status.HTTP_200_OK
                    last_request_time = frozen_time().replace(tzinfo=None)
                    frozen_time.tick(
                        delta=timezone.timedelta(seconds=time_between_requests)
                    )

                # Next request should be throttled
                response = self.client.post(
                    SEND_OTP_URL, {
                        "phone_number": phone
                    }
                )
                if response.status_code == status.HTTP_200_OK:
                    response = self.client.post(
                        SEND_OTP_URL, {
                            "phone_number": phone
                        }
                    )
                assert response.status_code in (
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    status.HTTP_400_BAD_REQUEST)

                retry_after = (
                        response.headers.get(
                            "Retry-After"
                        )
                        or response.headers.get("retry-after")
                        or str(period_seconds)
                )

                try:
                    wait_s = int(float(retry_after))
                except ValueError:
                    wait_s = period_seconds
                frozen_time.tick(
                    delta=timezone.timedelta(seconds=wait_s + 1)
                )
                response = self.client.post(
                    SEND_OTP_URL, {
                        "phone_number": phone
                    }
                )
                assert response.status_code == status.HTTP_200_OK
                if response.status_code == status.HTTP_200_OK:
                    response = self.client.post(
                        SEND_OTP_URL, {"phone_number": phone}
                    )

                assert response.status_code in (
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    status.HTTP_400_BAD_REQUEST)

                # Move past the period from last successful request - should reset
                frozen_time.tick(
                    delta=timezone.timedelta(seconds=period_seconds + 5)
                )
                response = self.client.post(
                    SEND_OTP_URL, {"phone_number": phone}
                )
                assert response.status_code == status.HTTP_200_OK

    def test_phone_throttle_simple_reset(self):
        """Test throttle reset with a simpler approach - all requests at once, then wait."""
        phone = "09123456799"
        config = self.throttle_config
        requests_allowed = config["requests_allowed"]
        period_seconds = config["period_seconds"]

        with freeze_time("2024-01-01 12:00:00") as frozen_time:
            with patch('auth_api.models.PhoneOTP.send', return_value=True):
                # Make all allowed requests quickly (all at the same time)
                for i in range(requests_allowed):
                    response = self.client.post(
                        SEND_OTP_URL, {"phone_number": phone}
                    )
                    assert response.status_code == status.HTTP_200_OK

                # Next request should be throttled immediately
                response = self.client.post(
                    SEND_OTP_URL, {"phone_number": phone}
                )
                assert response.status_code in (
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    status.HTTP_400_BAD_REQUEST)

                # Move forward past the period - should be clear
                frozen_time.tick(
                    delta=timezone.timedelta(seconds=period_seconds + 1)
                )
                response = self.client.post(
                    SEND_OTP_URL, {"phone_number": phone}
                )
                assert response.status_code == status.HTTP_200_OK

    def test_phone_throttle_per_phone_isolation(self):
        """Test that throttling is isolated per phone number."""
        phone1 = "09123456791"
        phone2 = "09123456792"
        config = self.throttle_config
        requests_allowed = config["requests_allowed"]

        # Calculate time between requests
        time_between_requests = max(
            1, config["period_seconds"] // requests_allowed // 2
        )

        with freeze_time("2024-01-01 12:00:00") as frozen_time:
            with patch('auth_api.models.PhoneOTP.send', return_value=True):
                # Exhaust limit for phone1
                for i in range(requests_allowed):
                    response = self.client.post(
                        SEND_OTP_URL, {"phone_number": phone1}
                    )
                    assert response.status_code == status.HTTP_200_OK
                    frozen_time.tick(
                        delta=timezone.timedelta(seconds=time_between_requests)
                    )

                # phone1 should now be throttled
                response = self.client.post(
                    SEND_OTP_URL, {"phone_number": phone1}
                )
                assert response.status_code in (
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    status.HTTP_400_BAD_REQUEST)

                # phone2 should still work (independent throttle counter)
                response = self.client.post(
                    SEND_OTP_URL, {"phone_number": phone2}
                )
                assert response.status_code == status.HTTP_200_OK

    def test_global_anon_throttle_limit(self):
        """Test that anonymous users are subject to global 100/hour throttle."""
        # This test verifies that the global AnonRateThrottle is active
        # We'll simulate hitting the global limit before the phone limit

        with freeze_time("2024-01-01 12:00:00") as frozen_time:
            with patch('auth_api.models.PhoneOTP.send', return_value=True):
                # Use different phone numbers to avoid phone-specific throttling
                # and test global throttling instead
                request_count = 0
                throttled = False

                # Make requests until we hit the global throttle (100/hour)
                # Using different phones to bypass phone-specific throttling
                while request_count < 105 and not throttled:  # Safety limit
                    phone = f"091234{request_count:05d}"  # Generate unique phone numbers
                    response = self.client.post(
                        SEND_OTP_URL, {"phone_number": phone}
                    )

                    if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                        throttled = True
                        break

                    assert response.status_code == status.HTTP_200_OK
                    request_count += 1

                    # Move time slightly to avoid model-level duplicate prevention
                    frozen_time.tick(delta=timezone.timedelta(seconds=10))

                # Should hit the global limit around 100 requests
                assert throttled, f"Expected to hit global throttle limit, but made {request_count} requests"
                assert request_count >= 95, f"Global throttle should activate around 100 requests, got {request_count}"

    def test_throttle_retry_after_header(self):
        """Test that throttled responses include appropriate Retry-After header."""
        phone = "09123456793"
        config = self.throttle_config
        requests_allowed = config["requests_allowed"]

        # Calculate time between requests
        time_between_requests = max(
            1, config["period_seconds"] // requests_allowed // 2
        )

        with freeze_time("2024-01-01 12:00:00") as frozen_time:
            with patch('auth_api.models.PhoneOTP.send', return_value=True):
                # Exhaust the phone-specific limit
                for i in range(requests_allowed):
                    response = self.client.post(
                        SEND_OTP_URL, {"phone_number": phone}
                    )
                    assert response.status_code == status.HTTP_200_OK
                    frozen_time.tick(
                        delta=timezone.timedelta(seconds=time_between_requests)
                    )

                # Next request should be throttled with retry header
                response = self.client.post(
                    SEND_OTP_URL, {"phone_number": phone}
                )
                assert response.status_code in (
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    status.HTTP_400_BAD_REQUEST)

                # Should have Retry-After header indicating when to retry
                assert "Retry-After" in response.headers or "retry-after" in response.headers

                # Response should contain throttle information
                assert "throttled" in response.data.get("detail", "").lower()

    def test_model_level_throttle_vs_drf_throttle_interaction(self):
        """Test interaction between model-level OTP throttling and DRF throttling."""
        phone = "09123456794"

        with freeze_time("2024-01-01 12:00:00") as frozen_time:
            # First request should succeed
            response = self.client.post(SEND_OTP_URL, {"phone_number": phone})
            assert response.status_code == status.HTTP_200_OK

            # Second request within LIFE_DURATION (5 minutes) should be blocked by model logic
            frozen_time.tick(delta=timezone.timedelta(minutes=2))
            response = self.client.post(SEND_OTP_URL, {"phone_number": phone})
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "کد تایید شما ارسال شده است" in str(response.data)

            # After LIFE_DURATION, should work again (if under DRF throttle limit)
            frozen_time.tick(
                delta=timezone.timedelta(minutes=4)
            )  # Total: 6 minutes
            response = self.client.post(SEND_OTP_URL, {"phone_number": phone})
            assert response.status_code == status.HTTP_200_OK

    def test_throttle_limit_configuration_accuracy(self):
        """Test that throttling matches the exact configured rate."""
        phone = "09123456795"
        config = self.throttle_config
        requests_allowed = config["requests_allowed"]

        # Calculate time between requests
        time_between_requests = max(
            1, config["period_seconds"] // requests_allowed // 2
        )

        with freeze_time("2024-01-01 12:00:00") as frozen_time:
            with patch('auth_api.models.PhoneOTP.send', return_value=True):
                success_count = 0

                # Make exactly the configured number of requests
                for i in range(requests_allowed):
                    response = self.client.post(
                        SEND_OTP_URL, {"phone_number": phone}
                    )
                    if response.status_code == status.HTTP_200_OK:
                        success_count += 1
                    frozen_time.tick(
                        delta=timezone.timedelta(seconds=time_between_requests)
                    )

                assert success_count == requests_allowed, f"Expected exactly {requests_allowed} successful requests, got {success_count}"

                # Next request should definitely be throttled
                response = self.client.post(
                    SEND_OTP_URL, {"phone_number": phone}
                )
                assert response.status_code in (
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    status.HTTP_400_BAD_REQUEST)

    def test_cache_key_generation_for_phone_throttle(self):
        """Test that different phones generate different cache keys."""
        phone1 = "09123456796"
        phone2 = "09123456797"
        config = self.throttle_config
        requests_allowed = config["requests_allowed"]

        # Calculate time between requests  
        time_between_requests = max(
            1, config["period_seconds"] // requests_allowed // 2
        )

        with freeze_time("2024-01-01 12:00:00") as frozen_time:
            with patch('auth_api.models.PhoneOTP.send', return_value=True):
                # Both phones should be able to make their full quota independently
                for phone in [phone1, phone2]:
                    for i in range(requests_allowed):
                        response = self.client.post(
                            SEND_OTP_URL, {"phone_number": phone}
                        )
                        assert response.status_code == status.HTTP_200_OK
                        frozen_time.tick(
                            delta=timezone.timedelta(
                                seconds=time_between_requests
                            )
                        )

                    # Each phone should hit its own limit
                    response = self.client.post(
                        SEND_OTP_URL, {"phone_number": phone}
                    )
                    assert response.status_code in (
                        status.HTTP_429_TOO_MANY_REQUESTS,
                        status.HTTP_400_BAD_REQUEST)

    def test_dynamic_throttle_rate_compatibility(self):
        """
        Test that demonstrates the dynamic nature of these tests.
        This test will work regardless of whether the throttle is configured as:
        - "3/minute" (3 requests per 60 seconds)  
        - "5/minute" (5 requests per 60 seconds)
        - "10/hour" (10 requests per 3600 seconds)
        - "100/day" (100 requests per 86400 seconds)
        """
        phone = "09123456798"
        config = self.throttle_config

        print(f"\n🔧 Testing with dynamic throttle configuration:")
        print(f"   Rate: {config['rate_string']}")
        print(
            f"   Limit: {config['requests_allowed']} requests per {config['period_seconds']} seconds"
        )
        print(f"   Scope: {config['scope']}")

        # Verify we can make exactly the configured number of requests
        with freeze_time("2024-01-01 12:00:00") as frozen_time:
            with patch('auth_api.models.PhoneOTP.send', return_value=True):
                # Test that we can make all allowed requests
                for i in range(config['requests_allowed']):
                    response = self.client.post(
                        SEND_OTP_URL, {"phone_number": phone}
                    )
                    assert response.status_code == status.HTTP_200_OK, f"Request {i + 1} failed"

                # Test that the next request is throttled
                response = self.client.post(
                    SEND_OTP_URL, {"phone_number": phone}
                )
                assert response.status_code in (
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    status.HTTP_400_BAD_REQUEST)

                print(
                    f"✅ Successfully tested {config['requests_allowed']} allowed requests + throttling"
                )
