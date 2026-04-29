# wallets/api/public/v1/schema/installment.py

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)

from wallets.api.public.v1.serializers import InstallmentSerializer

WALLET_INSTALLMENTS_TAG = "Wallet · Installments"

installments_schema = extend_schema(
    tags=[WALLET_INSTALLMENTS_TAG],
    summary="List user's installments",
    description="Return the authenticated user's installments with optional filters.",
    parameters=[
        OpenApiParameter(
            name="status",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Installment status filter. Example: `unpaid` or `paid`.",
        ),
        OpenApiParameter(
            name="due_from",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description="Lower bound for due date in `YYYY-MM-DD` format.",
        ),
        OpenApiParameter(
            name="due_to",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description="Upper bound for due date in `YYYY-MM-DD` format.",
        ),
        OpenApiParameter(
            name="ordering",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Ordering by due date: `due_date` or `-due_date`.",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=InstallmentSerializer(many=True),
            description="Installment list returned successfully.",
        )
    },
    examples=[
        OpenApiExample(
            "InstallmentListResponse",
            response_only=True,
            value=[
                {
                    "id": 10,
                    "due_date": "2025-11-12",
                    "amount": 500000,
                    "amount_paid": 0,
                    "status": "unpaid",
                    "paid_at": None,
                    "transaction_id": None,
                    "is_overdue": False,
                    "current_penalty": 0,
                    "penalty_amount": 0,
                    "total_due": 500000,
                    "note": "",
                }
            ],
        )
    ],
)

installment_viewset_schema = extend_schema_view(
    list=installments_schema,
    retrieve=extend_schema(
        tags=[WALLET_INSTALLMENTS_TAG],
        summary="Retrieve an installment",
        description="Return a single installment belonging to the authenticated user.",
        responses={
            200: OpenApiResponse(
                response=InstallmentSerializer,
                description="Installment retrieved successfully.",
            ),
            404: OpenApiResponse(description="Installment not found."),
        },
    ),
)
