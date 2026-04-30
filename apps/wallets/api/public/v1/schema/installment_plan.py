# apps/wallets/api/public/v1/schema/installment_plan.py

from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)

from apps.wallets.api.public.v1.serializers import (
    InstallmentPlanSerializer,
    InstallmentSerializer,
)

WALLET_INSTALLMENT_PLANS_TAG = "Wallet · Installment Plans"

installment_plans_schema = extend_schema(
    tags=[WALLET_INSTALLMENT_PLANS_TAG],
    summary="List user's installment plans",
    description="Return installment plans of the authenticated user.",
)

plan_installments_action_schema = extend_schema(
    tags=[WALLET_INSTALLMENT_PLANS_TAG],
    summary="List installments of a plan",
    description="Return installments belonging to the selected installment plan.",
    parameters=[
        OpenApiParameter(
            name="ordering",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Ordering by due date: `due_date` or `-due_date`.",
        )
    ],
    responses={
        200: OpenApiResponse(
            response=InstallmentSerializer(many=True),
            description="Installments returned successfully.",
        )
    },
)

installment_plan_viewset_schema = extend_schema_view(
    list=installment_plans_schema,
    retrieve=extend_schema(
        tags=[WALLET_INSTALLMENT_PLANS_TAG],
        summary="Retrieve an installment plan",
        description="Return a single installment plan belonging to the authenticated user.",
        responses={
            200: OpenApiResponse(
                response=InstallmentPlanSerializer,
                description="Installment plan retrieved successfully.",
            ),
            404: OpenApiResponse(description="Installment plan not found."),
        },
    ),
)
