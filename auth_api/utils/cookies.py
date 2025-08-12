# auth_api/utils/cookies.py

from datetime import datetime, timezone

from django.conf import settings
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken


def _default_refresh_cookie_max_age():
    return int(jwt_settings.REFRESH_TOKEN_LIFETIME.total_seconds())


def _resolve_cookie_max_age(refresh_token_str: str) -> int:
    try:
        token = RefreshToken(refresh_token_str)
        exp_ts = int(token['exp'])
        now_ts = int(datetime.now(timezone.utc).timestamp())
        remaining = max(exp_ts - now_ts, 0)
        return remaining or _default_refresh_cookie_max_age()
    except Exception:
        return _default_refresh_cookie_max_age()


def set_refresh_cookie(
        response, refresh_token_str: str, max_age: int | None = None
):
    if max_age is None:
        configured = getattr(settings, "REFRESH_COOKIE_MAX_AGE", None)
        if isinstance(configured, int) and configured > 0:
            max_age = configured
        else:
            max_age = _resolve_cookie_max_age(refresh_token_str)

    response.set_cookie(
        key=getattr(settings, "REFRESH_COOKIE_NAME", "sp_refresh"),
        value=refresh_token_str,
        max_age=max_age,
        path=getattr(settings, "REFRESH_COOKIE_PATH", "/"),
        secure=getattr(settings, "REFRESH_COOKIE_SECURE", True),
        httponly=getattr(settings, "REFRESH_COOKIE_HTTPONLY", True),
        samesite=getattr(settings, "REFRESH_COOKIE_SAMESITE", "Strict"),
    )


def delete_refresh_cookie(response):
    response.delete_cookie(
        key=getattr(settings, "REFRESH_COOKIE_NAME", "sp_refresh"),
        path=getattr(settings, "REFRESH_COOKIE_PATH", "/"),
        domain=getattr(settings, "REFRESH_COOKIE_DOMAIN", None),
        samesite=getattr(settings, "REFRESH_COOKIE_SAMESITE", "Strict"),
    )
