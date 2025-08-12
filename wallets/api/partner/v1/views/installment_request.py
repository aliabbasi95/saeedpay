# wallets/api/partner/v1/views/installment_request.py
from urllib.parse import urlencode

from django.conf import settings
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    extend_schema, OpenApiParameter,
    OpenApiResponse,
)
from rest_framework import status
from rest_framework.serializers import Serializer

from lib.cas_auth.views import PublicAPIView, PublicGetAPIView
from merchants.permissions import IsMerchant
from profiles.models import Profile
from store.authentication import StoreApiKeyAuthentication
from wallets.api.partner.v1.serializers import (
    InstallmentRequestCreateSerializer,
    InstallmentRequestVerifyResponseSerializer,
)
from wallets.api.public.v1.serializers import \
    (
    InstallmentRequestDetailSerializer, InstallmentRequestListItemSerializer,
)
from wallets.models import InstallmentRequest
from wallets.services import finalize_installment_request
from wallets.utils.choices import InstallmentRequestStatus
from wallets.utils.consts import FRONTEND_INSTALLMENT_REQUEST_DETAIL_URL


@extend_schema(
    request=InstallmentRequestCreateSerializer,
    tags=["Wallet · Installment Requests (Store API)"],
    summary="ایجاد درخواست اقساطی از سمت فروشگاه",
    description="فروشگاه با استفاده از API Key یک درخواست اقساطی برای مشتری ثبت می‌کند"
)
class InstallmentRequestCreateView(PublicAPIView):
    authentication_classes = [StoreApiKeyAuthentication]
    permission_classes = [IsMerchant]
    serializer_class = InstallmentRequestCreateSerializer

    def perform_save(self, serializer):
        store = self.request.store
        data = serializer.validated_data
        external_guid = data["guid"]

        try:
            profile = Profile.objects.get(national_id=data["national_id"])
            customer = profile.user.customer
        except Exception:
            self.response_data = {"detail": "مشتری با این کد ملی یافت نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return
        if InstallmentRequest.objects.filter(
                store=store, external_guid=external_guid
        ).exists():
            self.response_data = {"detail": "درخواست تکراری است."}
            self.response_status = 409
            return

        req = InstallmentRequest.objects.create(
            store=store,
            customer=customer,
            national_id=data["national_id"],
            external_guid=external_guid,
            store_proposed_amount=data["amount"],
            contract=data["contract"],
        )
        query_string = urlencode({"reference_code": req.reference_code})
        payment_url = f"{settings.FRONTEND_BASE_URL}{FRONTEND_INSTALLMENT_REQUEST_DETAIL_URL}?{query_string}"

        self.response_data = {
            "installment_request_id": req.id,
            "reference_code": req.reference_code,
            "store_proposed_amount": req.store_proposed_amount,
            "payment_url": payment_url,
            "status": req.status,
        }
        self.response_status = status.HTTP_201_CREATED


@extend_schema(
    responses=InstallmentRequestDetailSerializer,
    tags=["Wallet · Installment Requests (Partner)"],
    summary="دریافت اطلاعات درخواست اقساطی",
    description="مشاهده اطلاعات درخواست اقساطی ایجاد شده توسط فروشگاه با کد پیگیری"
)
class InstallmentRequestRetrieveView(PublicGetAPIView):
    authentication_classes = [StoreApiKeyAuthentication]
    permission_classes = [IsMerchant]
    serializer_class = InstallmentRequestDetailSerializer

    def get(self, request, reference_code):
        qs = InstallmentRequest.objects.filter(
            reference_code=reference_code,
            store=request.store
        )
        obj = qs.first()

        if not obj:
            self.response_data = {"detail": "درخواست اقساطی یافت نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response

        self.response_data = self.get_serializer(obj).data
        self.response_status = status.HTTP_200_OK
        return self.response


@extend_schema(
    tags=["Wallet · Installment Requests (Partner)"],
    summary="تایید نهایی درخواست اقساطی توسط فروشگاه",
    description="تایید فروشگاه برای نهایی‌سازی درخواست اقساطی پس از تایید کاربر",
    request=None,  # ← بدنه‌ای نداریم
    parameters=[
        OpenApiParameter(
            name="reference_code",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.PATH,
            description="کد مرجع یکتای درخواست اقساطی"
        )
    ],
    responses={
        200: OpenApiResponse(InstallmentRequestListItemSerializer),
        400: OpenApiResponse(
            description="درخواست هنوز توسط کاربر تایید نشده است."
        ),
        404: OpenApiResponse(description="درخواست اقساطی یافت نشد.")
    }
)
class InstallmentRequestVerifyView(PublicAPIView):
    authentication_classes = [StoreApiKeyAuthentication]
    serializer_class = InstallmentRequestListItemSerializer
    permission_classes = [IsMerchant]

    def post(self, request, reference_code):
        req = InstallmentRequest.objects.filter(
            reference_code=reference_code,
            store=request.store
        ).first()
        if not req:
            self.response_data = {"detail": "درخواست اقساطی یافت نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response

        if req.status != InstallmentRequestStatus.AWAITING_MERCHANT_CONFIRMATION:
            self.response_data = {
                "detail": "درخواست هنوز توسط کاربر تایید نشده است."
            }
            self.response_status = status.HTTP_400_BAD_REQUEST
            return self.response

        finalize_installment_request(req)

        self.response_data = self.get_serializer(req).data
        self.response_status = status.HTTP_200_OK
        return self.response
