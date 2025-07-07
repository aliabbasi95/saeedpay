# auth_api/tests/public/v1/serializers/test_token_refresh.py

import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken

from auth_api.api.public.v1.serializers.refresh import \
    CustomTokenRefreshSerializer
from auth_api.tokens import CustomRefreshToken


@pytest.mark.django_db
class TestCustomTokenRefreshSerializer:

    def test_valid_refresh_token(self):
        user = get_user_model().objects.create(username="09120000000")
        refresh = str(CustomRefreshToken.for_user(user))

        serializer = CustomTokenRefreshSerializer(data={"refresh": refresh})
        assert serializer.is_valid()
        assert "access" in serializer.validated_data

    def test_missing_refresh_field(self):
        serializer = CustomTokenRefreshSerializer(data={})
        assert not serializer.is_valid()
        assert "refresh" in serializer.errors

    def test_invalid_refresh_token_format(self):
        data = {"refresh": "✺✺✺invalid.token✺✺✺"}

        with pytest.raises(InvalidToken) as exc:
            serializer = CustomTokenRefreshSerializer(data=data)
            serializer.is_valid(raise_exception=True)
        assert "invalid" in str(exc.value).lower()

    def test_blacklisted_refresh_token(self):
        user = get_user_model().objects.create(username="09120000001")
        refresh_obj = CustomRefreshToken.for_user(user)
        refresh_obj.blacklist()

        with pytest.raises(InvalidToken):
            serializer = CustomTokenRefreshSerializer(
                data={"refresh": str(refresh_obj)}
            )
            serializer.is_valid(raise_exception=True)

    def test_refresh_token_for_deleted_user(self):
        user = get_user_model().objects.create(username="09120000002")
        refresh = str(CustomRefreshToken.for_user(user))
        user.delete()

        with pytest.raises(get_user_model().DoesNotExist):
            serializer = CustomTokenRefreshSerializer(
                data={"refresh": refresh}
            )
            serializer.is_valid(raise_exception=True)

    def test_refresh_token_for_inactive_user(self):
        user = get_user_model().objects.create(
            username="09120000003", is_active=False
        )
        refresh = str(CustomRefreshToken.for_user(user))

        with pytest.raises(AuthenticationFailed) as exc_info:
            serializer = CustomTokenRefreshSerializer(
                data={"refresh": refresh}
            )
            serializer.is_valid(raise_exception=True)

        assert "No active account" in str(exc_info.value)

    def test_access_token_used_as_refresh(self):
        user = get_user_model().objects.create(username="09120000004")
        access = str(CustomRefreshToken.for_user(user).access_token)

        with pytest.raises(InvalidToken):
            serializer = CustomTokenRefreshSerializer(data={"refresh": access})
            serializer.is_valid(raise_exception=True)
