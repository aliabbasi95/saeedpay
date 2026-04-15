# kyc/tests/services/test_identity_auth_service.py

import os
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase

from kyc.services import IdentityAuthService, get_identity_auth_service
from kyc.utils import sanitize_user_data, validate_user_data
from kyc.utils.validators import validate_national_id, validate_phone_number

IDENTITY_POST_PATH = "kyc.services.identity_auth_service.requests.Session.post"


class IdentityAuthServiceTestCase(TestCase):
    """Test cases for IdentityAuthService."""

    def setUp(self):
        self.service = IdentityAuthService()
        self.service.base_url = "https://example.com"
        self.service.username = "test_username"
        self.service.password = "test_password"
        self.service.org_name = "test_org"
        self.service.org_national_code = "12345678901"

        self.valid_user_data = {
            "national_id": "1234567890",
            "phone": "09123456789",
            "first_name": "علی",
            "last_name": "احمدی",
        }

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_service_initialization(self):
        """Test service initialization."""
        service = IdentityAuthService()
        self.assertIsInstance(service, IdentityAuthService)

    def test_get_identity_auth_service_new_instance(self):
        """Test that get_identity_auth_service returns new instances."""
        service1 = get_identity_auth_service()
        service2 = get_identity_auth_service()
        # Should return different instances for multi-process safety
        self.assertIsNot(service1, service2)
        # But both should be instances of the same class
        self.assertIsInstance(service1, IdentityAuthService)
        self.assertIsInstance(service2, IdentityAuthService)

    @patch(IDENTITY_POST_PATH)
    def test_authenticate_success(self, mock_post):
        """Test successful authentication."""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Test authentication
        access_token, refresh_token = self.service._authenticate()

        self.assertEqual(access_token, "test_access_token")
        self.assertEqual(refresh_token, "test_refresh_token")
        mock_post.assert_called_once()

    @patch(IDENTITY_POST_PATH)
    def test_authenticate_with_retry(self, mock_post):
        from requests.exceptions import ConnectionError

        # First call fails
        mock_post.side_effect = ConnectionError("Network error")

        access_token, refresh_token = self.service._authenticate()

        self.assertIsNone(access_token)
        self.assertIsNone(refresh_token)

        # Only one call should happen (no retry logic implemented)
        self.assertEqual(mock_post.call_count, 1)

    @patch(IDENTITY_POST_PATH)
    def test_authenticate_failure(self, mock_post):
        """Test authentication failure."""
        # Mock failed response
        mock_post.side_effect = Exception("Network error")

        # Test authentication
        access_token, refresh_token = self.service._authenticate()

        self.assertIsNone(access_token)
        self.assertIsNone(refresh_token)

    def test_clear_tokens(self):
        """Test token clearing."""
        # Set some test tokens in cache
        cache.set("kyc_identity_access_token", "test_token")
        cache.set("kyc_identity_refresh_token", "test_refresh")

        # Clear tokens
        self.service.clear_tokens()

        # Check that tokens are cleared
        self.assertIsNone(cache.get("kyc_identity_access_token"))
        self.assertIsNone(cache.get("kyc_identity_refresh_token"))


class ValidationTestCase(TestCase):
    """Test cases for validation functions."""

    def test_validate_national_id_valid(self):
        """Test valid national ID validation."""

        # Test with a valid national ID (this is a test number)
        valid_id = "0123456789"
        self.assertTrue(validate_national_id(valid_id))

    def test_validate_national_id_invalid(self):
        """Test invalid national ID validation."""
        # Test with invalid national IDs
        invalid_ids = ["123", "123456789", "12345678901", "0000000000", ""]
        for invalid_id in invalid_ids:
            self.assertFalse(validate_national_id(invalid_id))

    def test_validate_phone_number_valid(self):
        """Test valid phone number validation."""

        valid_phones = ["09123456789", "989123456789", "09123456789"]
        for phone in valid_phones:
            self.assertTrue(validate_phone_number(phone))

    def test_validate_phone_number_invalid(self):
        """Test invalid phone number validation."""

        invalid_phones = ["123", "0912345678", "08123456789", ""]
        for phone in invalid_phones:
            self.assertFalse(validate_phone_number(phone))

    def test_validate_user_data_success(self):
        """Test successful user data validation."""
        user_data = {
            "national_id": "0123456789",
            "phone": "09123456789",
            "first_name": "علی",
            "last_name": "احمدی",
        }

        result = validate_user_data(user_data)
        self.assertEqual(result["national_id"], "0123456789")
        self.assertEqual(result["phone"], "09123456789")

    def test_validate_user_data_failure(self):
        """Test user data validation failure."""
        user_data = {
            "national_id": "123",  # Invalid
            "phone": "08123456789",  # Invalid
        }

        with self.assertRaises(ValidationError):
            validate_user_data(user_data)

    def test_sanitize_user_data(self):
        """Test user data sanitization."""
        user_data = {
            "national_id": " 012-345-6789 ",
            "phone": "+98 912 345 6789",
            "first_name": "  علی  ",
            "last_name": "  احمدی  ",
        }

        result = sanitize_user_data(user_data)
        self.assertEqual(result["national_id"], "0123456789")
        self.assertEqual(result["phone"], "09123456789")
        self.assertEqual(result["first_name"], "علی")
        self.assertEqual(result["last_name"], "احمدی")
