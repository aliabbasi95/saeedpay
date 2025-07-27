# auth_api/api/public/v1/views/reset_password.py
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny

from auth_api.api.public.v1.serializers import ResetPasswordSerializer
from auth_api.utils.throttles import OTPPhoneRateThrottle
from lib.cas_auth.views import PublicAPIView


@extend_schema(
    request=ResetPasswordSerializer,
    responses={
        200: OpenApiResponse(description="Password reset successfully."),
        400: OpenApiResponse(description="Validation failed."),
    },
    tags=["Authentication"]
)
class ResetPasswordView(PublicAPIView):
    permission_classes = (AllowAny,)
    serializer_class = ResetPasswordSerializer
    throttle_classes = [OTPPhoneRateThrottle]

    def perform_save(self, serializer):
        serializer.save()
        self.response_data = {"detail": "رمز عبور با موفقیت بازنشانی شد."}
        self.response_status = status.HTTP_200_OK
