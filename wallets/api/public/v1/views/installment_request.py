# wallets/api/public/v1/views/installment_request.py

from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status

from lib.cas_auth.views import PublicAPIView, PublicGetAPIView
from wallets.api.public.v1.serializers import (
    InstallmentRequestDetailSerializer,
    InstallmentRequestConfirmSerializer,
)
from wallets.models import InstallmentRequest
from wallets.services import notify_store_user_confirmed
from wallets.utils.choices import InstallmentRequestStatus


@extend_schema(
    responses=InstallmentRequestDetailSerializer,
    tags=["Wallet · Installment Requests (Public)"],
    summary="دریافت اطلاعات درخواست اقساطی",
    description="دریافت اطلاعات اولیه درخواست اقساطی با استفاده از کد پیگیری"
)
class InstallmentRequestDetailView(PublicGetAPIView):
    serializer_class = InstallmentRequestDetailSerializer

    def get(self, request, reference_code):
        obj = InstallmentRequest.objects.filter(
            reference_code=reference_code,
            customer=request.user.customer
        ).first()
        if not obj:
            self.response_data = {"detail": "درخواست اقساطی یافت نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response

        self.response_data = self.get_serializer(obj).data
        self.response_status = status.HTTP_200_OK
        return self.response


@extend_schema(
    request=InstallmentRequestConfirmSerializer,
    responses={200: OpenApiResponse(description="خروجی شبیه‌سازی اقساط")},
    tags=["Wallet · Installment Requests (Public)"],
    summary="محاسبه اقساط قبل از تایید",
    description="محاسبه جدول اقساط براساس اطلاعات ورودی کاربر، بدون ذخیره‌سازی"
)
class InstallmentCalculationView(PublicAPIView):
    serializer_class = InstallmentRequestConfirmSerializer

    def post(self, request, reference_code):
        obj = InstallmentRequest.objects.filter(
            reference_code=reference_code,
            customer=request.user.customer
        ).first()
        if not obj:
            self.response_data = {"detail": "درخواست اقساطی یافت نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response
        serializer = self.get_serializer(
            data=request.data,
            context={"installment_request": obj}
        )
        serializer.is_valid(raise_exception=True)

        self.response_data = serializer.validated_data["installment_plan"]
        self.response_status = status.HTTP_200_OK
        return self.response


@extend_schema(
    request=InstallmentRequestConfirmSerializer,
    responses={
        200: OpenApiResponse(
            description="درخواست تایید شد و منتظر تایید فروشنده است"
        )
    },
    tags=["Wallet · Installment Requests (Public)"],
    summary="تایید نهایی درخواست اقساطی توسط کاربر",
    description="کاربر پس از بررسی جدول اقساط، درخواست خود را تایید می‌کند تا برای تایید نهایی به فروشگاه ارسال شود"
)
class InstallmentRequestConfirmView(PublicAPIView):
    serializer_class = InstallmentRequestConfirmSerializer

    def post(self, request, reference_code):
        obj = InstallmentRequest.objects.filter(
            reference_code=reference_code,
            customer=request.user.customer
        ).first()
        if not obj:
            self.response_data = {"detail": "درخواست اقساطی یافت نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response

        serializer = self.get_serializer(
            data=request.data,
            context={"installment_request": obj}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        obj.confirmed_amount = data["confirmed_amount"]
        obj.duration_months = data["duration_months"]
        obj.period_months = data["period_months"]
        obj.status = InstallmentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        obj.user_confirmed_at = timezone.now()
        obj.save()

        notify_store_user_confirmed(obj)

        self.response_data = {
            "detail": "درخواست اقساطی با موفقیت تایید شد.",
            **data["installment_plan"]
        }
        self.response_status = status.HTTP_200_OK
        return self.response
