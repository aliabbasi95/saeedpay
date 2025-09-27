# auth_api/api/public/v1/views/refresh.py

from datetime import datetime, timezone, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import TokenError

from auth_api.tokens import CustomRefreshToken
from auth_api.utils.cookies import set_refresh_cookie
from lib.cas_auth.views import PublicAPIView

MAX_SESSION_LIFETIME = getattr(
    settings, "MAX_SESSION_LIFETIME", timedelta(hours=24)
)


@extend_schema(
    request=None,
    responses={
        200: OpenApiResponse(description="New access token issued."),
        401: OpenApiResponse(description="Session expired or token invalid.")
    },
    tags=["Authentication"]
)
class TokenRefreshView(PublicAPIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "sp_refresh")
        refresh_str = request.COOKIES.get(cookie_name)
        if not refresh_str:
            return Response(
                {"detail": "رفرش‌توکن در کوکی یافت نشد."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        def _unauth(detail):
            resp = Response(
                {"detail": detail}, status=status.HTTP_401_UNAUTHORIZED
            )
            resp.delete_cookie(cookie_name, path="/")
            return resp

        try:
            old_refresh = CustomRefreshToken(refresh_str)

            try:
                old_refresh.check_blacklist()
            except TokenError:
                return _unauth("رفرش‌توکن نامعتبر یا بلاک شده است.")

            orig_iat = old_refresh.payload.get("orig_iat")
            if orig_iat is None:
                return _unauth("اطلاعات شروع نشست موجود نیست.")
            session_start = datetime.fromtimestamp(orig_iat, tz=timezone.utc)
            if datetime.now(
                    tz=timezone.utc
            ) - session_start > MAX_SESSION_LIFETIME:
                return _unauth("طول عمر نشست تمام شده است. دوباره وارد شوید.")

            user_id = old_refresh.payload.get("user_id")
            if not user_id:
                return _unauth("user_id در توکن یافت نشد.")
            User = get_user_model()
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return _unauth("کاربر مربوط به توکن یافت نشد.")

            issued_is_active = bool(
                old_refresh.payload.get(
                    "is_active_at_issue",
                    old_refresh.payload.get(
                        "is_active",
                        old_refresh.payload.get("active", True)
                    )
                )
            )
            if issued_is_active and not user.is_active:
                try:
                    old_refresh.blacklist()
                except Exception:
                    pass
                return _unauth("حساب کاربری غیرفعال است.")

            try:
                old_refresh.blacklist()
            except Exception:
                pass

            new_refresh = CustomRefreshToken.for_user(user)
            access = str(new_refresh.access_token)

        except TokenError:
            return _unauth("رفرش‌توکن نامعتبر یا منقضی است.")
        except Exception:
            return Response(
                {"detail": "خطا در پردازش توکن."},
                status=status.HTTP_400_BAD_REQUEST
            )

        resp = Response(
            {"access": access, "token_type": "Bearer"},
            status=status.HTTP_200_OK
        )
        set_refresh_cookie(resp, str(new_refresh))
        return resp
