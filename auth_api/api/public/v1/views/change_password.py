from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status

from auth_api.api.public.v1.serializers import ChangePasswordSerializer
from lib.cas_auth.views import PublicAPIView


@extend_schema(
    request=ChangePasswordSerializer,
    responses={
        200: OpenApiResponse(description="Password changed successfully."),
        400: OpenApiResponse(description="Validation failed."),
    },
    tags=["Authentication"]
)
class ChangePasswordView(PublicAPIView):
    serializer_class = ChangePasswordSerializer

    def perform_save(self, serializer):
        serializer.save()
        self.response_data = {"detail": "رمز عبور با موفقیت تغییر یافت."}
        self.response_status = status.HTTP_200_OK
