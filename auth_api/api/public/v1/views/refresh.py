# auth_api/api/public/v1/views/refresh.py

from datetime import datetime, timezone, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import TokenError

from auth_api.tokens import CustomRefreshToken  # مهم
from auth_api.utils.cookies import set_refresh_cookie
from lib.cas_auth.views import PublicAPIView

MAX_SESSION_LIFETIME = getattr(
    settings, "MAX_SESSION_LIFETIME", timedelta(hours=24)
)


@extend_schema(
    request=None,
    responses={
        200: OpenApiResponse(description="New access token issued."),
        401: OpenApiResponse(description="Session expired or token invalid."),
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

        try:
            old_refresh = CustomRefreshToken(refresh_str)
            orig_iat = old_refresh.payload.get("orig_iat")
            if orig_iat is None:
                return Response(
                    {"detail": "اطلاعات شروع نشست موجود نیست."},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            session_start = datetime.fromtimestamp(orig_iat, tz=timezone.utc)
            if datetime.now(
                    tz=timezone.utc
            ) - session_start > MAX_SESSION_LIFETIME:
                return Response(
                    {"detail": "طول عمر نشست تمام شده است. دوباره وارد شوید."},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            user_id = old_refresh.payload.get("user_id")
            if not user_id:
                return Response(
                    {"detail": "user_id در توکن یافت نشد."},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            User = get_user_model()
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response(
                    {"detail": "کاربر مربوط به توکن یافت نشد."},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            old_refresh.blacklist()

            new_refresh = CustomRefreshToken.for_user(user)
            access = str(new_refresh.access_token)

        except TokenError:
            return Response(
                {"detail": "رفرش‌توکن نامعتبر یا منقضی است."},
                status=status.HTTP_401_UNAUTHORIZED
            )
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
