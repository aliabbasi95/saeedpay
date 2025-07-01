# auth_api/api/public/v1/views/logout.py
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from auth_api.api.public.v1.serializers import LogoutSerializer
from lib.cas_auth.views import PublicAPIView


class LogoutView(PublicAPIView):
    serializer_class = LogoutSerializer

    def perform_save(self, serializer):
        refresh_token = serializer.validated_data["refresh"]

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            self.response_data = {"detail": "توکن نامعتبر یا منقضی شده است."}
            self.response_status = status.HTTP_400_BAD_REQUEST
            return

        self.response_data = {"detail": "خروج با موفقیت انجام شد."}
        self.response_status = status.HTTP_205_RESET_CONTENT
