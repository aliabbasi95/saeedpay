# wallets/api/partner/v1/schema/payment.py

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view

from wallets.api.partner.v1.serializers import (
    PaymentActionResponseSerializer,
    PaymentRequestCreateResponseSerializer,
    PaymentRequestCreateSerializer,
    PaymentRequestPartnerDetailSerializer,
)

partner_payment_request_viewset_schema = extend_schema_view(
    create=extend_schema(
        tags=["Wallet · Payment Requests (Partner)"],
        summary="ایجاد درخواست پرداخت",
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
        tags=["Wallet · Payment Requests (Partner)"],
        summary="جزییات درخواست پرداخت",
        responses={200: PaymentRequestPartnerDetailSerializer},
    ),
)

partner_payment_verify_schema = extend_schema(
    tags=["Wallet · Payment Requests (Partner)"],
    summary="تایید نهایی پرداخت",
    description="پس از پرداخت موفق توسط مشتری، فروشگاه پرداخت را نهایی می‌کند.",
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
