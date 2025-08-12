# auth_api/api/public/v1/views/register_merchant.py

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny

from auth_api.api.public.v1.views.mixins import IssueTokensResponseMixin
from auth_api.api.public.v1.serializers import RegisterMerchantSerializer
from lib.cas_auth.views import PublicAPIView


@extend_schema(
    request=RegisterMerchantSerializer,
    responses={
        201: OpenApiResponse(description="User registered successfully."),
        400: OpenApiResponse(description="Validation failed."),
    },
    tags=["Authentication"]
)
class RegisterMerchantView(IssueTokensResponseMixin, PublicAPIView):
    permission_classes = (AllowAny,)
    serializer_class = RegisterMerchantSerializer
    default_success_status = status.HTTP_201_CREATED

    def perform_save(self, serializer):
        user = serializer.save()
        self.response = self.build_tokens_response(serializer, user)
