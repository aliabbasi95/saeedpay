# auth_api/api/public/v1/views/logout.py
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from auth_api.api.public.v1.serializers import LogoutSerializer
from lib.cas_auth.views import PublicAPIView


@extend_schema(
    request=None,
    responses={
        205: OpenApiResponse(description="Logout successful."),
        400: OpenApiResponse(
            description="Refresh token is missing or invalid."
        ),
    },
    tags=["Authentication"]
)
class LogoutView(PublicAPIView):
    serializer_class = LogoutSerializer

    def perform_save(self, serializer):
        refresh_token = serializer.validated_data["refresh"]

        try:
            token = RefreshToken(refresh_token)
            token_user_id = token.get("user_id", None)

            if not token_user_id:
                self.response_data = {"detail": "user_id در توکن یافت نشد."}
                self.response_status = status.HTTP_400_BAD_REQUEST
                return

            if str(self.request.user.id) != str(token_user_id):
                self.response_data = {
                    "detail": "توکن متعلق به کاربر جاری نیست."
                }
                self.response_status = status.HTTP_400_BAD_REQUEST
                return

            token.blacklist()

        except TokenError:
            self.response_data = {"detail": "توکن نامعتبر یا منقضی شده است."}
            self.response_status = status.HTTP_400_BAD_REQUEST
            return

        self.response_data = {"detail": "خروج با موفقیت انجام شد."}
        self.response_status = status.HTTP_205_RESET_CONTENT
