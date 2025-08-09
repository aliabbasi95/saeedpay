# auth_api/api/public/v1/views/logout.py

from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from auth_api.utils.cookies import delete_refresh_cookie
from lib.cas_auth.views import PublicAPIView


@extend_schema(
    request=None,
    responses={
        205: OpenApiResponse(description="Logout successful."),
        200: OpenApiResponse(description="Logout successful."),
    },
    tags=["Authentication"]
)
class LogoutView(PublicAPIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "sp_refresh")
        refresh_str = request.COOKIES.get(cookie_name)

        if refresh_str:
            try:
                token = RefreshToken(refresh_str)
                try:
                    token.blacklist()
                except Exception:
                    pass
            except TokenError:
                pass

        resp = Response(
            {"detail": "خروج انجام شد."}, status=status.HTTP_205_RESET_CONTENT
        )
        delete_refresh_cookie(resp)
        return resp
