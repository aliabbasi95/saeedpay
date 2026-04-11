# wallets/api/public/v1/schema/payment_requests.py

from drf_spectacular.utils import OpenApiParameter, extend_schema

from wallets.api.public.v1.serializers.payment import (
    PaymentActionResponseSerializer,
    PaymentConfirmSerializer,
    PaymentRequestDetailWithWalletsSerializer,
    PaymentRequestListItemSerializer,
)
from wallets.api.public.v1.serializers.payment_pos import (
    MerchantPosPaymentRequestCreateResponseSerializer,
    MerchantPosPaymentRequestCreateSerializer,
    MerchantPosPaymentRequestDetailSerializer,
    MerchantPosPaymentRequestListItemSerializer,
)

payment_list_schema = extend_schema(
    summary="لیست درخواست‌های پرداخت مشتری",
    parameters=[
        OpenApiParameter(name="status", required=False, type=str),
        OpenApiParameter(name="store_id", required=False, type=int),
        OpenApiParameter(name="q", required=False, type=str),
        OpenApiParameter(name="created_from", required=False, type=str),
        OpenApiParameter(name="created_to", required=False, type=str),
        OpenApiParameter(name="expires_from", required=False, type=str),
        OpenApiParameter(name="expires_to", required=False, type=str),
        OpenApiParameter(
            name="ordering",
            required=False,
            type=str,
            description="created_at, -created_at, amount, -amount",
        ),
    ],
    responses={200: PaymentRequestListItemSerializer(many=True)},
)

payment_retrieve_schema = extend_schema(
    summary="جزییات درخواست پرداخت",
    responses={200: PaymentRequestDetailWithWalletsSerializer},
)

payment_confirm_schema = extend_schema(
    summary="تایید و پرداخت درخواست پرداخت",
    request=PaymentConfirmSerializer,
    responses={200: PaymentActionResponseSerializer},
)

merchant_pos_payment_create_schema = extend_schema(
    summary="ایجاد درخواست پرداخت حضوری QR توسط فروشنده",
    request=MerchantPosPaymentRequestCreateSerializer,
    responses={201: MerchantPosPaymentRequestCreateResponseSerializer},
)

merchant_pos_payment_list_schema = extend_schema(
    summary="لیست درخواست‌های پرداخت حضوری QR فروشنده",
    parameters=[
        OpenApiParameter(name="store_id", required=False, type=int),
        OpenApiParameter(name="status", required=False, type=str),
        OpenApiParameter(name="q", required=False, type=str),
        OpenApiParameter(name="created_from", required=False, type=str),
        OpenApiParameter(name="created_to", required=False, type=str),
        OpenApiParameter(
            name="ordering",
            required=False,
            type=str,
            description="created_at, -created_at, amount, -amount",
        ),
    ],
    responses={200: MerchantPosPaymentRequestListItemSerializer(many=True)},
)

merchant_pos_payment_retrieve_schema = extend_schema(
    summary="جزییات درخواست پرداخت حضوری QR فروشنده",
    responses={200: MerchantPosPaymentRequestDetailSerializer},
)
