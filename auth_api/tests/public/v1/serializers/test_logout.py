# auth_api/tests/public/v1/serializers/test_logout.py
import pytest
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

from auth_api.api.public.v1.serializers import LogoutSerializer


@pytest.mark.django_db
class TestLogoutSerializer:

    def test_valid_refresh_token(self):
        user = get_user_model().objects.create(username="09121111111")
        refresh = RefreshToken.for_user(user)

        serializer = LogoutSerializer(data={"refresh": str(refresh)})
        assert serializer.is_valid()
        assert serializer.validated_data["refresh"] == str(refresh)

    def test_missing_refresh_field(self):
        serializer = LogoutSerializer(data={})
        assert not serializer.is_valid()
        assert "refresh" in serializer.errors

    def test_refresh_token_only_spaces(self):
        serializer = LogoutSerializer(data={"refresh": "   "})
        assert not serializer.is_valid()
        assert "refresh" in serializer.errors

    @pytest.mark.parametrize("invalid_type", [None, 123, 12.5, [], {}, True])
    def test_refresh_token_wrong_type(self, invalid_type):
        serializer = LogoutSerializer(data={"refresh": invalid_type})
        assert not serializer.is_valid()
        assert "refresh" in serializer.errors

    def test_refresh_token_wrong_format(self):
        bad_token = "part1.part2"  # فقط ۲ بخش به‌جای ۳
        serializer = LogoutSerializer(data={"refresh": bad_token})
        assert not serializer.is_valid()
        assert "refresh" in serializer.errors
