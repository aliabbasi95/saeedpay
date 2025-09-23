# wallets/api/partner/v1/views/payment.py

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError

from lib.cas_auth.views import PublicAPIView
from merchants.permissions import IsMerchant
from store.authentication import StoreApiKeyAuthentication
from wallets.api.partner.v1.serializers import (
    PaymentRequestCreateSerializer,
    PaymentRequestCreateResponseSerializer,
    PaymentVerifyResponseSerializer, PaymentRequestPartnerDetailSerializer,
)
from wallets.models import PaymentRequest
from wallets.services.payment import (
    create_payment_request,
    verify_payment_request,
)
from wallets.utils.consts import FRONTEND_PAYMENT_DETAIL_URL


@extend_schema(
    request=PaymentRequestCreateSerializer,
    responses=PaymentRequestCreateResponseSerializer,
    tags=["Wallet · Payment Requests (Partner)"],
    summary="ایجاد درخواست پرداخت",
    description="ایجاد یک درخواست پرداخت توسط فروشگاه با استفاده از API Key"
)
class PaymentRequestCreateView(PublicAPIView):
    authentication_classes = [StoreApiKeyAuthentication]
    permission_classes = [IsMerchant]
    serializer_class = PaymentRequestCreateSerializer

    def perform_save(self, serializer):
        store = self.request.store
        req = create_payment_request(
            store=store,
            amount=serializer.validated_data["amount"],
            return_url=serializer.validated_data.get("return_url"),
            description=serializer.validated_data.get("description", ""),
            external_guid=serializer.validated_data.get("external_guid"),
        )
        payment_url = f"{settings.FRONTEND_BASE_URL}{FRONTEND_PAYMENT_DETAIL_URL}{req.reference_code}/"
        self.response_data = PaymentRequestCreateResponseSerializer(
            {
                "payment_request_id": req.id,
                "payment_reference_code": req.reference_code,
                "amount": req.amount,
                "description": req.description,
                "return_url": req.return_url,
                "status": req.status,
                "payment_url": payment_url,
            }
        ).data

        self.response_status = status.HTTP_201_CREATED


@extend_schema(
    responses=PaymentRequestPartnerDetailSerializer,
    tags=["Wallet · Payment Requests (Partner)"],
    summary="جزییات درخواست پرداخت (سمت فروشگاه)",
    description="بازیابی اطلاعات کامل درخواست پرداخت با reference_code از سمت فروشگاه"
)
class PaymentRequestRetrieveView(PublicAPIView):
    authentication_classes = [StoreApiKeyAuthentication]
    permission_classes = [IsMerchant]
    serializer_class = PaymentRequestPartnerDetailSerializer

    def get(self, request, reference_code):
        pr = PaymentRequest.objects.filter(
            reference_code=reference_code, store=request.store
        ).first()
        if not pr:
            self.response_data = {"detail": "درخواست پرداخت پیدا نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response
        self.response_data = self.serializer_class(pr).data
        self.response_status = status.HTTP_200_OK
        return self.response


@extend_schema(
    responses=PaymentVerifyResponseSerializer,
    tags=["Wallet · Payment Requests (Partner)"],
    summary="تایید نهایی پرداخت",
    description="پس از پرداخت موفق توسط مشتری، فروشگاه با این API پرداخت را تایید نهایی می‌کند"
)
class PaymentRequestVerifyView(PublicAPIView):
    authentication_classes = [StoreApiKeyAuthentication]
    permission_classes = [IsMerchant]
    serializer_class = PaymentVerifyResponseSerializer

    def post(self, request, reference_code):
        try:
            payment_request = PaymentRequest.objects.get(
                reference_code=reference_code
            )
        except PaymentRequest.DoesNotExist:
            self.response_data = {"detail": "درخواست پرداخت پیدا نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response

        try:
            txn = verify_payment_request(payment_request)
            self.response_data = self.serializer_class(
                {
                    "detail": "پرداخت نهایی شد.",
                    "payment_reference_code": payment_request.reference_code,
                    "transaction_reference_code": txn.reference_code,
                    "amount": payment_request.amount
                }
            ).data
            self.response_status = status.HTTP_200_OK
        except ValidationError as e:
            message = e.detail[0] if isinstance(e.detail, list) else str(
                e.detail
            )
            self.response_data = {"detail": message}
            self.response_status = status.HTTP_400_BAD_REQUEST

        return self.response
