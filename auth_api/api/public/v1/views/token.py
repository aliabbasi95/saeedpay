# auth_api/api/public/v1/views/token.py
from rest_framework_simplejwt.views import TokenRefreshView

from auth_api.api.public.v1.serializers.refresh import \
    CustomTokenRefreshSerializer


class SecureTokenRefreshView(TokenRefreshView):
    serializer_class = CustomTokenRefreshSerializer
