# wallets/api/public/v1/views/payment.py
from rest_framework import status
from rest_framework.permissions import AllowAny

from lib.cas_auth.views import PublicAPIView, PublicGetAPIView
from wallets.api.public.v1.serializers import (
    WalletSerializer,
    PaymentConfirmSerializer,
    PaymentRequestDetailSerializer,
    PaymentConfirmResponseSerializer,
)
from wallets.models import Wallet, PaymentRequest
from wallets.services.payment import (
    pay_payment_request, check_and_expire_payment_request,
)
from wallets.utils.choices import OwnerType


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
