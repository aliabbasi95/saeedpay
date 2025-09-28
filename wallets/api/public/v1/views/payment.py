# wallets/api/public/v1/views/payment.py

from drf_spectacular.utils import (
    extend_schema, OpenApiResponse,
    OpenApiExample,
)
from rest_framework import status

from lib.cas_auth.views import PublicAPIView, PublicGetAPIView
from wallets.api.public.v1.serializers import (
    PaymentConfirmSerializer,
    PaymentRequestDetailWithWalletsSerializer,
    PaymentConfirmResponseSerializer,
)
from wallets.models import Wallet, PaymentRequest
from wallets.services.payment import (
    pay_payment_request, check_and_expire_payment_request,
)


@extend_schema(
    responses={
        200: OpenApiResponse(
            response=PaymentRequestDetailWithWalletsSerializer,
            description=(
                    "Returns payment request details. If the caller is authenticated, "
                    "`available_wallets` contains only wallets able to fully cover the amount. "
                    "For credit wallets, capacity is based on active credit limit."
            ),
            examples=[
                OpenApiExample(
                    "Unauthenticated (no available_wallets)",
                    value={
                        "reference_code": "PR123456",
                        "amount": 10000,
                        "description": "Purchase",
                        "store_id": 42,
                        "store_name": "Demo Store",
                        "status": "created",
                        "expires_at": "2025-09-27T12:34:56Z"
                    }
                ),
                OpenApiExample(
                    "Authenticated (with available_wallets)",
                    value={
                        "reference_code": "PR123456",
                        "amount": 10000,
                        "description": "Purchase",
                        "store_id": 42,
                        "store_name": "Demo Store",
                        "status": "created",
                        "expires_at": "2025-09-27T12:34:56Z",
                        "available_wallets": [
                            {
                                "id": 101,
                                "wallet_number": "619230317637",
                                "kind": "cash",
                                "kind_display": "نقدی",
                                "owner_type": "customer",
                                "owner_type_display": "مشتری",
                                "spendable_amount": 50000,
                                "created_at": "2025-09-27T10:00:00Z",
                                "updated_at": "2025-09-27T10:00:00Z"
                            },
                            {
                                "id": 202,
                                "wallet_number": "610000000002",
                                "kind": "credit",
                                "kind_display": "اعتباری",
                                "owner_type": "customer",
                                "owner_type_display": "مشتری",
                                "spendable_amount": 30000,
                                "created_at": "2025-09-20T08:00:00Z",
                                "updated_at": "2025-09-26T09:30:00Z"
                            }
                        ]
                    }
                ),
            ],
        ),
        400: OpenApiResponse(
            description="Payment request expired or invalid."
        ),
        404: OpenApiResponse(description="Payment request not found."),
    },
    tags=["Wallet · Payment Requests"],
    summary="Get payment request details",
    description=(
            "Returns payment request details by `reference_code`. "
            "If the caller is authenticated, also returns `available_wallets` "
            "filtered to wallets that can fully cover the amount."
    ),
)
class PaymentRequestDetailView(PublicGetAPIView):
    serializer_class = PaymentRequestDetailWithWalletsSerializer

    def get(self, request, reference_code):
        try:
            pr = PaymentRequest.objects.select_related("store").get(
                reference_code=reference_code,
                customer=self.request.user.customer
            )
        except PaymentRequest.DoesNotExist:
            self.response_data = {"detail": "درخواست پرداخت پیدا نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response

        try:
            check_and_expire_payment_request(pr)
        except Exception as e:
            self.response_data = {
                "detail": str(e),
                "reference_code": pr.reference_code,
                "return_url": pr.return_url
            }
            self.response_status = status.HTTP_400_BAD_REQUEST
            return self.response

        data = self.get_serializer(pr, context={"request": request}).data
        self.response_data.update(data)
        self.response_status = status.HTTP_200_OK
        return self.response


@extend_schema(
    request=PaymentConfirmSerializer,
    responses={
        200: PaymentConfirmResponseSerializer,
        400: OpenApiResponse(
            description="Validation error or business rule violation."
        ),
        404: OpenApiResponse(description="Payment request not found."),
    },
    tags=["Wallet · Payment Requests"],
    summary="Confirm & pay",
    description="Confirms and pays the payment request using the selected wallet.",
)
class PaymentConfirmView(PublicAPIView):
    serializer_class = PaymentConfirmSerializer

    def post(self, request, reference_code):
        try:
            payment_request = PaymentRequest.objects.get(
                reference_code=reference_code,
                customer=self.request.user.customer
            )
        except PaymentRequest.DoesNotExist:
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
        try:
            wallet = Wallet.objects.get(id=wallet_id, user=self.request.user)
        except Wallet.DoesNotExist:
            self.response_data = {
                "detail": "کیف پول پیدا نشد یا متعلق به شما نیست."
            }
            self.response_status = status.HTTP_400_BAD_REQUEST
            return self.response
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
