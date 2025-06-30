# auth_api/api/public/v1/views/logout.py
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from lib.cas_auth.views import PublicAPIView


class LogoutView(PublicAPIView):

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {"detail": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {"detail": "Logout successful."},
            status=status.HTTP_205_RESET_CONTENT
        )
