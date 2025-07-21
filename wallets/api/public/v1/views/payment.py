# wallets/api/internal/v1/views/payment.py
from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny

from lib.cas_auth.views import PublicAPIView, PublicGetAPIView
from merchants.authentication import MerchantAPIKeyAuthentication
from merchants.permissions import IsMerchant
from wallets.api.public.v1.serializers import (
    PaymentRequestCreateSerializer,
    WalletSerializer,
    PaymentConfirmSerializer,
    PaymentRequestDetailSerializer, PaymentRequestCreateResponseSerializer,
    PaymentConfirmResponseSerializer, PaymentVerifyResponseSerializer,
)
from wallets.models import Wallet, PaymentRequest
from wallets.services.payment import (
    create_payment_request,
    pay_payment_request, verify_payment_request,
    check_and_expire_payment_request,
)
from wallets.utils.choices import OwnerType
from wallets.utils.consts import FRONTEND_PAYMENT_DETAIL_URL


class PaymentRequestCreateView(PublicAPIView):
    authentication_classes = [MerchantAPIKeyAuthentication]
    permission_classes = [IsMerchant]
    serializer_class = PaymentRequestCreateSerializer

    def perform_save(self, serializer):
        merchant = self.request.user
        req = create_payment_request(
            merchant=merchant,
            amount=serializer.validated_data["amount"],
            return_url=serializer.validated_data.get("return_url"),
            description=serializer.validated_data.get("description", ""),
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


class PaymentRequestDetailView(PublicGetAPIView):
    permission_classes = [AllowAny]
    serializer_class = PaymentRequestDetailSerializer

    def get(self, request, reference_code):
        payment_req = PaymentRequest.objects.filter(
            reference_code=reference_code
        ).first()
        if not payment_req:
            self.response_data = {"detail": "درخواست پرداخت پیدا نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response

        try:
            check_and_expire_payment_request(payment_req)
        except Exception as e:
            self.response_data = {
                "detail": str(e),
                "reference_code": payment_req.reference_code,
                "return_url": payment_req.return_url
            }
            self.response_status = status.HTTP_400_BAD_REQUEST
            return self.response

        data = self.get_serializer(payment_req).data
        user = request.user if request.user and request.user.is_authenticated else None
        if user:
            wallets = Wallet.objects.filter(
                user=user, owner_type=OwnerType.CUSTOMER
            )
            wallets = [
                w for w in wallets if w.available_balance >= payment_req.amount
            ]

            available_wallets = WalletSerializer(data=wallets, many=True)
            available_wallets.is_valid()
            data["available_wallets"] = available_wallets.data
        self.response_data.update(data)
        self.response_status = status.HTTP_200_OK

        return self.response


class PaymentConfirmView(PublicAPIView):
    serializer_class = PaymentConfirmSerializer

    def post(self, request, reference_code):
        payment_request = PaymentRequest.objects.get(
            reference_code=reference_code
        )
        if not payment_request:
            self.response_data = {"detail": "درخواست پرداخت پیدا نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response

        serializer = self.get_serializer(
            data=request.data, context={'request': self.request}
        )
        serializer.is_valid(raise_exception=True)

        wallet_id = serializer.validated_data["wallet_id"]
        try:
            check_and_expire_payment_request(payment_request)
        except Exception as e:
            self.response_data = {
                "detail": str(e),
                "reference_code": payment_request.reference_code,
                "return_url": payment_request.return_url
            }
            self.response_status = status.HTTP_400_BAD_REQUEST
            return self.response
        wallet = Wallet.objects.get(id=wallet_id, user=self.request.user)
        try:
            txn = pay_payment_request(
                payment_request, self.request.user, wallet
            )
        except Exception as e:
            self.response_data = {"detail": str(e)}
            self.response_status = status.HTTP_400_BAD_REQUEST
            return self.response
        self.response_data = PaymentConfirmResponseSerializer(
            {
                "detail": "پرداخت با موفقیت انجام شد.",
                "payment_reference_code": payment_request.reference_code,
                "transaction_reference_code": txn.reference_code,
                "return_url": payment_request.return_url
            }
        ).data

        self.response_status = status.HTTP_200_OK
        return self.response


class PaymentRequestVerifyView(PublicAPIView):
    authentication_classes = [MerchantAPIKeyAuthentication]
    permission_classes = [IsMerchant]
    serializer_class = PaymentVerifyResponseSerializer

    def post(self, request, reference_code):
        payment_request = PaymentRequest.objects.get(
            reference_code=reference_code
        )
        if not payment_request:
            self.response_data = {"detail": "درخواست پرداخت پیدا نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
        else:
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
