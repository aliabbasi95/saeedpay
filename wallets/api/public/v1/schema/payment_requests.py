# wallets/api/public/v1/schema/payment_requests.py

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)

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

WALLET_PAYMENT_REQUESTS_TAG = "Wallet · Payment Requests"
WALLET_MERCHANT_POS_TAG = "Wallet · Merchant POS"

payment_list_schema = extend_schema(
    tags=[WALLET_PAYMENT_REQUESTS_TAG],
    summary="List customer's payment requests",
    description=(
        "Return payment requests belonging to the authenticated customer. "
        "Supports filtering by status, store, date ranges, and ordering."
    ),
    parameters=[
        OpenApiParameter(name="status", required=False, type=OpenApiTypes.STR),
        OpenApiParameter(name="store_id", required=False, type=OpenApiTypes.INT),
        OpenApiParameter(name="q", required=False, type=OpenApiTypes.STR),
        OpenApiParameter(
            name="created_from",
            required=False,
            type=OpenApiTypes.STR,
            description="Datetime/date lower bound.",
        ),
        OpenApiParameter(
            name="created_to",
            required=False,
            type=OpenApiTypes.STR,
            description="Datetime/date upper bound.",
        ),
        OpenApiParameter(
            name="expires_from",
            required=False,
            type=OpenApiTypes.STR,
            description="Datetime/date lower bound.",
        ),
        OpenApiParameter(
            name="expires_to",
            required=False,
            type=OpenApiTypes.STR,
            description="Datetime/date upper bound.",
        ),
        OpenApiParameter(
            name="ordering",
            required=False,
            type=OpenApiTypes.STR,
            description="`created_at`, `-created_at`, `amount`, `-amount`.",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=PaymentRequestListItemSerializer(many=True),
            description="Payment request list returned successfully.",
        ),
        401: OpenApiResponse(description="Authentication required."),
    },
)

payment_retrieve_schema = extend_schema(
    tags=[WALLET_PAYMENT_REQUESTS_TAG],
    summary="Retrieve a payment request",
    description=(
        "Return details of a payment request by reference code. "
        "Public QR payment requests can be viewed without authentication, "
        "but payment eligibility depends on the authenticated user."
    ),
    responses={
        200: OpenApiResponse(
            response=PaymentRequestDetailWithWalletsSerializer,
            description="Payment request retrieved successfully.",
        ),
        404: OpenApiResponse(description="Payment request not found."),
    },
)

payment_confirm_schema = extend_schema(
    tags=[WALLET_PAYMENT_REQUESTS_TAG],
    summary="Confirm and pay a payment request",
    description=(
        "Pay a payment request using a selected wallet and OTP code. "
        "For online flow, the request moves to awaiting store confirmation. "
        "For QR POS flow, payment is completed directly."
    ),
    request=PaymentConfirmSerializer,
    responses={
        200: OpenApiResponse(
            response=PaymentActionResponseSerializer,
            description="Payment completed successfully.",
        ),
        400: OpenApiResponse(
            response=PaymentActionResponseSerializer,
            description="Validation, business rule, or internal error response.",
        ),
        401: OpenApiResponse(description="Authentication required."),
        410: OpenApiResponse(
            response=PaymentActionResponseSerializer,
            description="Expired payment request.",
        ),
    },
    examples=[
        OpenApiExample(
            "PaymentConfirmRequest",
            request_only=True,
            value={"wallet_id": 12, "code": "12345"},
        )
    ],
)

payment_request_viewset_schema = extend_schema_view(
    list=payment_list_schema,
    retrieve=payment_retrieve_schema,
)

merchant_pos_payment_create_schema = extend_schema(
    tags=[WALLET_MERCHANT_POS_TAG],
    summary="Create a merchant POS QR payment request",
    description=(
        "Create a QR POS payment request for one of the authenticated merchant's stores. "
        "The customer is not assigned at creation time; frontend uses the reference code "
        "to generate the QR."
    ),
    request=MerchantPosPaymentRequestCreateSerializer,
    responses={
        201: OpenApiResponse(
            response=MerchantPosPaymentRequestCreateResponseSerializer,
            description="Merchant POS payment request created successfully.",
        ),
        400: OpenApiResponse(
            response=PaymentActionResponseSerializer,
            description="Validation or business rule error.",
        ),
        404: OpenApiResponse(
            response=PaymentActionResponseSerializer,
            description="Store not found or does not belong to merchant.",
        ),
    },
)

merchant_pos_payment_list_schema = extend_schema(
    tags=[WALLET_MERCHANT_POS_TAG],
    summary="List merchant POS QR payment requests",
    description=(
        "Return QR POS payment requests belonging to the authenticated merchant. "
        "Supports filtering by store, status, dates, search, and ordering."
    ),
    parameters=[
        OpenApiParameter(name="store_id", required=False, type=OpenApiTypes.INT),
        OpenApiParameter(name="status", required=False, type=OpenApiTypes.STR),
        OpenApiParameter(name="q", required=False, type=OpenApiTypes.STR),
        OpenApiParameter(
            name="created_from",
            required=False,
            type=OpenApiTypes.STR,
            description="Datetime/date lower bound.",
        ),
        OpenApiParameter(
            name="created_to",
            required=False,
            type=OpenApiTypes.STR,
            description="Datetime/date upper bound.",
        ),
        OpenApiParameter(
            name="ordering",
            required=False,
            type=OpenApiTypes.STR,
            description="`created_at`, `-created_at`, `amount`, `-amount`.",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=MerchantPosPaymentRequestListItemSerializer(many=True),
            description="Merchant POS payment request list returned successfully.",
        ),
    },
)

merchant_pos_payment_retrieve_schema = extend_schema(
    tags=[WALLET_MERCHANT_POS_TAG],
    summary="Retrieve a merchant POS QR payment request",
    description=(
        "Return operational details of a merchant POS QR payment request for the owning merchant."
    ),
    responses={
        200: OpenApiResponse(
            response=MerchantPosPaymentRequestDetailSerializer,
            description="Merchant POS payment request retrieved successfully.",
        ),
        404: OpenApiResponse(description="Payment request not found."),
    },
)

merchant_pos_payment_cancel_schema = extend_schema(
    tags=[WALLET_MERCHANT_POS_TAG],
    summary="Cancel a merchant POS QR payment request",
    description=(
        "Cancel a QR POS payment request if it is still in a cancelable state."
    ),
    responses={
        200: OpenApiResponse(
            response=PaymentActionResponseSerializer,
            description="Merchant POS payment request cancelled successfully.",
        ),
        400: OpenApiResponse(
            response=PaymentActionResponseSerializer,
            description="Validation, business rule, or internal error response.",
        ),
        404: OpenApiResponse(description="Payment request not found."),
    },
)

merchant_pos_payment_viewset_schema = extend_schema_view(
    create=merchant_pos_payment_create_schema,
    list=merchant_pos_payment_list_schema,
    retrieve=merchant_pos_payment_retrieve_schema,
)
