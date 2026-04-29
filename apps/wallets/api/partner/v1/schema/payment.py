# wallets/api/partner/v1/schema/payment.py

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view

from wallets.api.partner.v1.serializers import (
    PaymentActionResponseSerializer,
    PaymentRequestCreateResponseSerializer,
    PaymentRequestCreateSerializer,
    PaymentRequestPartnerDetailSerializer,
)

PARTNER_PAYMENT_TAG = "Wallet · Partner Payment Requests"

partner_payment_request_viewset_schema = extend_schema_view(
    create=extend_schema(
        tags=[PARTNER_PAYMENT_TAG],
        summary="Create payment request",
        description="Create an online payment request for a customer from the partner API.",
        request=PaymentRequestCreateSerializer,
        responses={
            201: PaymentRequestCreateResponseSerializer,
            400: OpenApiResponse(
                response=PaymentActionResponseSerializer,
                description="Validation or business rule error.",
            ),
            404: OpenApiResponse(
                response=PaymentActionResponseSerializer,
                description="Customer not found.",
            ),
        },
    ),
    retrieve=extend_schema(
        tags=[PARTNER_PAYMENT_TAG],
        summary="Retrieve payment request",
        description="Return partner-facing details of a payment request.",
        responses={200: PaymentRequestPartnerDetailSerializer},
    ),
)

partner_payment_verify_schema = extend_schema(
    tags=[PARTNER_PAYMENT_TAG],
    summary="Verify payment",
    description="Finalize a successfully paid request from the partner side.",
    responses={
        200: PaymentActionResponseSerializer,
        400: OpenApiResponse(
            response=PaymentActionResponseSerializer,
            description="Validation or internal error response.",
        ),
        404: OpenApiResponse(
            response=PaymentActionResponseSerializer,
            description="Payment request not found.",
        ),
    },
)
