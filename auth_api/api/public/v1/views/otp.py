# auth_api/api/public/v1/views/otp.py

from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.permissions import AllowAny

from auth_api.api.public.v1.serializers import (
    SendOTPSerializer,
    SendUserOTPSerializer,
)
from auth_api.utils.throttles import OTPPhoneRateThrottle
from lib.cas_auth.views import PublicAPIView


@extend_schema(
    request=SendOTPSerializer,
    responses={
        200: OpenApiResponse(description="OTP sent successfully."),
        400: OpenApiResponse(description="OTP already sent."),
    },
    tags=["Authentication"],
)
class SendOTPView(PublicAPIView):
    permission_classes = (AllowAny,)
    serializer_class = SendOTPSerializer
    throttle_classes = PublicAPIView.throttle_classes + [
        OTPPhoneRateThrottle,
    ]

    def perform_save(self, serializer):
        serializer.save()
        self.response_data = {"detail": "کد تأیید با موفقیت ارسال شد."}
        self.response_status = status.HTTP_200_OK


@extend_schema(
    request=SendUserOTPSerializer,
    responses={
        200: OpenApiResponse(description="OTP sent successfully."),
        400: OpenApiResponse(description="OTP already sent."),
    },
    tags=["Authentication"],
)
class SendUserOTPView(PublicAPIView):
    permission_classes = (AllowAny,)
    serializer_class = SendUserOTPSerializer
    throttle_classes = PublicAPIView.throttle_classes + [
        OTPPhoneRateThrottle,
    ]

    def perform_save(self, serializer):
        serializer.save()
        self.response_data = {"detail": "کد تأیید با موفقیت ارسال شد."}
        self.response_status = status.HTTP_200_OK
