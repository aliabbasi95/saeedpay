# wallets/api/public/v1/schema/installment.py

from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiTypes,
    OpenApiResponse,
    OpenApiExample,
)

from wallets.api.public.v1.serializers import InstallmentSerializer

installments_schema = extend_schema(
    tags=["Wallet · Installments"],
    summary="List/Retrieve user's installments",
    description="اقساط کاربر با فیلتر وضعیت و بازه تاریخ سررسید.",
    parameters=[
        OpenApiParameter(
            name="status",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="unpaid | paid"
        ),
        OpenApiParameter(
            name="due_from",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description="YYYY-MM-DD"
        ),
        OpenApiParameter(
            name="due_to",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description="YYYY-MM-DD"
        ),
        OpenApiParameter(
            name="ordering",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="due_date | -due_date"
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=InstallmentSerializer(many=True), description="OK"
        )
    },
    examples=[
        OpenApiExample(
            "نمونه پاسخ",
            value=[{
                "id": 10, "due_date": "2025-11-12", "amount": 500000,
                "status": "unpaid", "current_penalty": 0
            }],
            response_only=True,
        )
    ],
)
