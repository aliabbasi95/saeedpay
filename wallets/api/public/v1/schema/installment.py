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
            "status", OpenApiParameter.QUERY, OpenApiTypes.STR,
            description="unpaid | paid"
        ),
        OpenApiParameter(
            "due_from", OpenApiParameter.QUERY, OpenApiTypes.DATE,
            description="YYYY-MM-DD"
        ),
        OpenApiParameter(
            "due_to", OpenApiParameter.QUERY, OpenApiTypes.DATE,
            description="YYYY-MM-DD"
        ),
        OpenApiParameter(
            "ordering", OpenApiParameter.QUERY, OpenApiTypes.STR,
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
