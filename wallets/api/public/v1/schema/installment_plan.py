# wallets/api/public/v1/schema/installment_plan.py

from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiTypes,
    OpenApiResponse,
)

from wallets.api.public.v1.serializers import (
    InstallmentSerializer,
)

installment_plans_schema = extend_schema(
    tags=["Wallet · Installment Plans"],
    summary="List/Retrieve user's installment plans",
    description="برنامه‌های اقساط کاربر با مرتب‌سازی.",
)

plan_installments_action_schema = extend_schema(
    tags=["Wallet · Installment Plans"],
    summary="List installments of a plan",
    parameters=[
        OpenApiParameter(
            name="ordering",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="due_date | -due_date"
        )
    ],
    responses={
        200: OpenApiResponse(
            response=InstallmentSerializer(many=True), description="OK"
        )
    },
)
