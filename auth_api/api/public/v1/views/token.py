# auth_api/api/public/v1/views/token.py
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework_simplejwt.views import TokenRefreshView

from auth_api.api.public.v1.serializers.refresh import \
    CustomTokenRefreshSerializer


@extend_schema(
    request=None,
    responses={
        200: OpenApiResponse(description="New access token issued."),
        401: OpenApiResponse(description="Session expired or token invalid."),
    },
    tags=["Authentication"]
)
class SecureTokenRefreshView(TokenRefreshView):
    serializer_class = CustomTokenRefreshSerializer
    schema = AutoSchema()
