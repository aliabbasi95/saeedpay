# auth_api/services/tokens.py

from datetime import datetime, timezone, timedelta
from typing import Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import TokenError

from auth_api.tokens import CustomRefreshToken


def rotate_refresh_cookie(
        request,
        *,
        max_session_lifetime: timedelta,
        cookie_name: str = None,
) -> Tuple[str, str]:
    """
    Validate current refresh cookie, enforce max session lifetime, blacklist it,
    and return (access_token_str, new_refresh_token_str).

    Raises:
        ValueError: when token is missing/invalid/expired or user not allowed.
        Exception:  for any unexpected error (caller should map to 400).
    """
    cookie_name = cookie_name or getattr(
        settings, "REFRESH_COOKIE_NAME", "sp_refresh"
    )
    refresh_str = request.COOKIES.get(cookie_name)
    if not refresh_str:
        raise ValueError("رفرش‌توکن در کوکی یافت نشد.")

    def _err(msg: str) -> ValueError:
        return ValueError(msg)

    try:
        old_refresh = CustomRefreshToken(refresh_str)

        # 1) blacklist check
        try:
            old_refresh.check_blacklist()
        except TokenError:
            raise _err("رفرش‌توکن نامعتبر یا بلاک شده است.")

        # 2) lifetime check
        orig_iat = old_refresh.payload.get("orig_iat")
        if orig_iat is None:
            raise _err("اطلاعات شروع نشست موجود نیست.")
        session_start = datetime.fromtimestamp(orig_iat, tz=timezone.utc)
        if datetime.now(
                tz=timezone.utc
        ) - session_start > max_session_lifetime:
            raise _err("طول عمر نشست تمام شده است. دوباره وارد شوید.")

        # 3) resolve user
        user_id = old_refresh.payload.get("user_id")
        if not user_id:
            raise _err("user_id در توکن یافت نشد.")

        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise _err("کاربر مربوط به توکن یافت نشد.")

        issued_is_active = bool(
            old_refresh.payload.get(
                "is_active_at_issue",
                old_refresh.payload.get(
                    "is_active", old_refresh.payload.get("active", True)
                ),
            )
        )
        if issued_is_active and not user.is_active:
            # Best-effort blacklist
            try:
                old_refresh.blacklist()
            except Exception:
                pass
            raise _err("حساب کاربری غیرفعال است.")

        # 4) rotate: blacklist old, mint new
        try:
            old_refresh.blacklist()
        except Exception:
            # ignore blacklist failures
            pass

        new_refresh = CustomRefreshToken.for_user(user)
        access = str(new_refresh.access_token)
        return access, str(new_refresh)

    except TokenError:
        raise _err("رفرش‌توکن نامعتبر یا منقضی است.")
