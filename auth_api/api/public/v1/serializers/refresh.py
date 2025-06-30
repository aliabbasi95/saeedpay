# auth_api/api/public/v1/serializers/refresh.py
from datetime import datetime, timedelta, timezone

from django.conf import settings
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

MAX_SESSION_LIFETIME = getattr(
    settings, "MAX_SESSION_LIFETIME", timedelta(hours=24)
)


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        try:
            refresh = RefreshToken(attrs["refresh"])
            orig_iat = refresh.payload.get("orig_iat")

            if orig_iat is None:
                raise InvalidToken("Missing session start time.")

            session_start = datetime.fromtimestamp(orig_iat, tz=timezone.utc)
            now = datetime.now(tz=timezone.utc)

            if now - session_start > MAX_SESSION_LIFETIME:
                raise InvalidToken(
                    "Maximum session lifetime exceeded. Please log in again."
                )

        except TokenError as e:
            raise InvalidToken(e.args[0])

        return super().validate(attrs)
