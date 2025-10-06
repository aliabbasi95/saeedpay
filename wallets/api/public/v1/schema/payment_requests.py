# wallets/api/public/v1/schema/payment_requests.py

from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
    OpenApiExample,
    OpenApiParameter,
    OpenApiTypes,
)

from wallets.api.public.v1.serializers.payment import (
    PaymentRequestListItemSerializer,
    PaymentRequestDetailWithWalletsSerializer,
    PaymentConfirmSerializer,
    PaymentConfirmResponseSerializer,
)

payment_list_schema = extend_schema(
    tags=["Wallet · Payment Requests"],
    summary="List user's payment requests",
    description="فهرست درخواست‌های پرداخت کاربر با فیلترها.",
    parameters=[
        OpenApiParameter(
            name="status", type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="created|completed|expired"
        ),
        OpenApiParameter(
            name="store_id", type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="Store ID"
        ),
        OpenApiParameter(
            name="q", type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
            description="reference_code icontains"
        ),
        OpenApiParameter(
            name="created_from", type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="ISO date/datetime"
        ),
        OpenApiParameter(
            name="created_to", type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="ISO date/datetime"
        ),
        OpenApiParameter(
            name="expires_from", type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="ISO date/datetime"
        ),
        OpenApiParameter(
            name="expires_to", type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="ISO date/datetime"
        ),
        OpenApiParameter(
            name="ordering", type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="-created_at|created_at|-amount|amount"
        ),
    ],
    responses={200: PaymentRequestListItemSerializer(many=True)},
)

payment_retrieve_schema = extend_schema(
    tags=["Wallet · Payment Requests"],
    summary="Get payment request details",
    description="جزییات یک درخواست پرداخت (به‌همراه کیف‌های مجاز کاربر).",
    responses={
        200: OpenApiResponse(
            response=PaymentRequestDetailWithWalletsSerializer
        ),
        404: OpenApiResponse(description="Not found"),
    },
    examples=[
        OpenApiExample(
            "Expired sample",
            value={
                "reference_code": "PR123456",
                "amount": 10000,
                "description": "Purchase",
                "store_id": 42,
                "store_name": "Demo Store",
                "status": "expired",
                "status_display": "منقضی‌شده",
                "expires_at": "2025-09-27T12:34:56Z",
                "paid_at": None,
                "can_pay": False,
                "reason": "expired",
                "available_wallets": [],
            },
            response_only=True,
        )
    ],
)

payment_confirm_schema = extend_schema(
    tags=["Wallet · Payment Requests"],
    summary="Confirm & pay",
    request=PaymentConfirmSerializer,
    responses={
        200: PaymentConfirmResponseSerializer,
        400: OpenApiResponse(description="Validation error"),
        404: OpenApiResponse(description="Not found"),
        410: OpenApiResponse(description="Expired"),
    },
    examples=[
        OpenApiExample(
            "OK", value={
                "detail": "پرداخت با موفقیت انجام شد.",
                "payment_reference_code": "PR123456",
                "transaction_reference_code": "TRX111222",
                "return_url": "https://example.com/orders/42",
            }, response_only=True
        )
    ],
)
