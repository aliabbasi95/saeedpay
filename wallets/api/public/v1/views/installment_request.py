# wallets/api/public/v1/views/installment_request.py
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, generics
from rest_framework.response import Response

from lib.cas_auth.views import PublicAPIView
from wallets.api.public.v1.serializers import (
    InstallmentRequestDetailSerializer,
    InstallmentRequestConfirmSerializer,
    InstallmentRequestUnderwriteSerializer,
    InstallmentRequestListItemSerializer,
    InstallmentRequestCalculationSerializer,
)
from wallets.models import InstallmentRequest


@extend_schema(
    tags=["Wallet · Installment Requests (Public)"],
    summary="لیست درخواست‌های اقساطی کاربر",
    description="بازگرداندن همه درخواست‌های اقساطی ثبت‌شده توسط کاربر",
    responses=InstallmentRequestListItemSerializer
)
class InstallmentRequestListView(generics.ListAPIView):
    serializer_class = InstallmentRequestListItemSerializer

    def get_queryset(self):
        return InstallmentRequest.objects.filter(
            customer=self.request.user.customer
        ).order_by("-created_at")


@extend_schema(
    tags=["Wallet · Installment Requests (Public)"],
    summary="جزییات یک درخواست اقساطی",
    description="دریافت جزییات یک درخواست اقساطی با کد پیگیری",
    responses=InstallmentRequestDetailSerializer
)
class InstallmentRequestDetailView(generics.RetrieveAPIView):
    serializer_class = InstallmentRequestDetailSerializer
    lookup_field = "reference_code"

    def get_queryset(self):
        return InstallmentRequest.objects.filter(
            customer=self.request.user.customer
        )


@extend_schema(
    tags=["Wallet · Installment Requests (Public)"],
    summary="محاسبه اقساط + دیتیل درخواست (بدون نیاز به VALIDATED)",
    description=(
        "این endpoint بر اساس وضعیت فعلی درخواست مبلغ مناسب را برای پیش‌نمایش انتخاب می‌کند:\n"
        "- اگر VALIDATED باشد، از مبلغ تاییدشده سیستم استفاده می‌کند.\n"
        "- در غیر این صورت از مبلغ درخواست‌شده کاربر یا مبلغ پیشنهادی فروشگاه استفاده می‌کند.\n"
        "هیچ داده‌ای ذخیره نمی‌شود."
    ),
    request=InstallmentRequestCalculationSerializer,
)
class InstallmentCalculationView(PublicAPIView):
    serializer_class = InstallmentRequestCalculationSerializer

    def post(self, request, reference_code):
        obj = InstallmentRequest.objects.filter(
            reference_code=reference_code,
            customer=request.user.customer
        ).first()
        if not obj:
            self.response_data = {"detail": "درخواست اقساطی یافت نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response

        ser = self.get_serializer(
            data=request.data,
            context={"installment_request": obj}
        )
        ser.is_valid(raise_exception=True)

        detail = InstallmentRequestDetailSerializer(obj).data
        preview = ser.preview()

        self.response_data = {
            "request": detail,
            "installment_preview": preview
        }
        self.response_status = status.HTTP_200_OK
        return self.response

@extend_schema(
    tags=["Wallet · Installment Requests (Public)"],
    summary="شروع/ارسال به اعتبارسنجی (پس‌زمینه)",
    description="ورودی کاربر ذخیره می‌شود و تسک Celery برای اعتبارسنجی اجرا می‌شود.",
    request=InstallmentRequestUnderwriteSerializer,
    responses={202: OpenApiResponse(description="اعتبارسنجی آغاز شد")}
)
class InstallmentUnderwriteView(PublicAPIView):
    serializer_class = InstallmentRequestUnderwriteSerializer

    def post(self, request, reference_code):
        obj = InstallmentRequest.objects.filter(
            reference_code=reference_code, customer=request.user.customer
        ).first()
        if not obj:
            return Response(
                {"detail": "درخواست اقساطی یافت نشد."},
                status=status.HTTP_404_NOT_FOUND
            )

        ser = self.get_serializer(
            data=request.data, context={"installment_request": obj}
        )
        ser.is_valid(raise_exception=True)
        payload = ser.persist_and_enqueue()
        return Response(payload, status=status.HTTP_202_ACCEPTED)


@extend_schema(
    tags=["Wallet · Installment Requests (Public)"],
    summary="تایید کاربر پس از اتمام اعتبارسنجی",
    description="کاربر نتیجه اعتبارسنجی را می‌پذیرد؛ درخواست به مرحله تایید فروشگاه می‌رود.",
    request=InstallmentRequestConfirmSerializer,
    responses={
        200: OpenApiResponse(description="تایید شد و منتظر تایید فروشگاه")
    }
)
class InstallmentRequestConfirmView(PublicAPIView):
    serializer_class = InstallmentRequestConfirmSerializer

    def post(self, request, reference_code):
        obj = InstallmentRequest.objects.filter(
            reference_code=reference_code,
            customer=request.user.customer
        ).first()
        if not obj:
            return Response(
                {"detail": "درخواست اقساطی یافت نشد."},
                status=status.HTTP_404_NOT_FOUND
            )

        ser = self.get_serializer(
            data=request.data or {}, context={"installment_request": obj}
        )
        ser.is_valid(raise_exception=True)
        payload = ser.confirm()
        return Response(payload, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Wallet · Installment Requests (Public)"],
    summary="لغو درخواست اقساطی",
    description="کاربر می‌تواند تا پیش از تایید فروشگاه درخواست را لغو کند.",
    request=None,
    responses={200: OpenApiResponse(description="لغو شد")}
)
class InstallmentRequestCancelView(generics.GenericAPIView):
    def post(self, request, reference_code):
        obj = InstallmentRequest.objects.filter(
            reference_code=reference_code,
            customer=request.user.customer
        ).first()
        if not obj:
            return Response(
                {"detail": "درخواست اقساطی یافت نشد."},
                status=status.HTTP_404_NOT_FOUND
            )

        if not obj.can_cancel():
            return Response(
                {"detail": "در این مرحله امکان لغو وجود ندارد."},
                status=status.HTTP_400_BAD_REQUEST
            )

        reason = request.data.get("reason", "") if hasattr(
            request, "data"
        ) else ""
        obj.mark_cancelled(reason=reason)
        return Response(
            {"detail": "درخواست با موفقیت لغو شد."}, status=status.HTTP_200_OK
        )
