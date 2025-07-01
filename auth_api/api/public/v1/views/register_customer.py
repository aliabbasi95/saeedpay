# auth_api/api/public/v1/views/register_customer.py
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny

from auth_api.api.public.v1.serializers import RegisterCustomerSerializer
from lib.cas_auth.views import PublicAPIView


@extend_schema(
    request=RegisterCustomerSerializer,
    responses={
        201: OpenApiResponse(description="User registered successfully."),
        400: OpenApiResponse(description="Validation failed."),
    },
    tags=["Authentication"]
)
class RegisterCustomerView(PublicAPIView):
    permission_classes = (AllowAny,)
    serializer_class = RegisterCustomerSerializer

    def perform_save(self, serializer):
        serializer.save()
        self.response_data = serializer.data
        self.response_status = status.HTTP_201_CREATED
