# auth_api/api/public/v1/views/otp.py
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.permissions import AllowAny

from auth_api.api.public.v1.serializers import SendOTPSerializer
from lib.cas_auth.views import PublicAPIView


@extend_schema(
    request=SendOTPSerializer,
    responses={
        200: OpenApiResponse(description="OTP sent successfully."),
        400: OpenApiResponse(description="OTP already sent."),
    },
    tags=["Authentication"]
)
class SendOTPView(PublicAPIView):
    permission_classes = (AllowAny,)
    serializer_class = SendOTPSerializer

    def perform_save(self, serializer):
        serializer.save()
        self.response_data = {"detail": "کد تأیید با موفقیت ارسال شد."}
        self.response_status = status.HTTP_200_OK
