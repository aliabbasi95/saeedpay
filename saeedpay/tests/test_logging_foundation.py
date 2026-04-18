# saeedpay/tests/test_logging_foundation.py

import pytest
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from saeedpay.logging import get_request_id, sanitize_log_value
from saeedpay.middleware import RequestIDMiddleware


@pytest.mark.django_db
class TestLoggingFoundation:
    def test_sanitize_log_value_masks_sensitive_fields(self):
        payload = {
            "phone_number": "09123456789",
            "access_token": "secret-token",
            "api_key": "super-secret",
            "normal_value": "ok",
            "nested": {
                "national_id": "1234567890",
                "event": "payment_created",
            },
        }

        sanitized = sanitize_log_value(payload)

        assert sanitized["phone_number"].endswith("6789")
        assert sanitized["phone_number"].startswith("*******")
        assert sanitized["access_token"] == "***"
        assert sanitized["api_key"] == "***"
        assert sanitized["normal_value"] == "ok"
        assert sanitized["nested"]["national_id"] == "***"
        assert sanitized["nested"]["event"] == "payment_created"

    @override_settings(REQUEST_ID_HEADER="X-Request-ID")
    def test_request_id_middleware_generates_and_returns_header(self):
        factory = RequestFactory()

        def get_response(request):
            assert hasattr(request, "request_id")
            assert get_request_id() == request.request_id
            return HttpResponse("ok")

        middleware = RequestIDMiddleware(get_response)
        request = factory.get("/test-path/")
        response = middleware(request)

        assert response.status_code == 200
        assert "X-Request-ID" in response
        assert response["X-Request-ID"]
        assert get_request_id() is None

    @override_settings(REQUEST_ID_HEADER="X-Request-ID")
    def test_request_id_middleware_reuses_incoming_header(self):
        factory = RequestFactory()
        incoming_request_id = "req-fixed-123"

        def get_response(request):
            assert request.request_id == incoming_request_id
            assert get_request_id() == incoming_request_id
            return HttpResponse("ok")

        middleware = RequestIDMiddleware(get_response)
        request = factory.get(
            "/test-path/",
            HTTP_X_REQUEST_ID=incoming_request_id,
        )
        response = middleware(request)

        assert response.status_code == 200
        assert response["X-Request-ID"] == incoming_request_id
        assert get_request_id() is None
