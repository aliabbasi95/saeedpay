# wallets/api/public/v1/views/installment_plan.py
# Read-only ViewSet for user's installment plans + nested installments action.

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from wallets.api.public.v1.serializers import (
    InstallmentPlanSerializer,
    InstallmentSerializer,
)
from wallets.filters import InstallmentPlanFilter
from wallets.models import InstallmentPlan, Installment


@extend_schema(
    tags=["Wallet · Installment Plans"],
    summary="List/Retrieve user's installment plans",
    description="Returns the authenticated user's installment plans. Filters + ordering supported."
)
class InstallmentPlanViewSet(
    ScopedThrottleByActionMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    """
    list:     Paginated list of user's installment plans.
    retrieve: Details of a single installment plan.
    installments: GET /installment-plans/{id}/installments/ -> installments in that plan.
    """
    serializer_class = InstallmentPlanSerializer
    lookup_field = "pk"

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = InstallmentPlanFilter
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    throttle_scope_map = {
        "default": "installment-plans-read",
        "list": "installment-plans-read",
        "retrieve": "installment-plans-read",
        "installments": "installments-read",
    }

    def get_queryset(self):
        return (
            InstallmentPlan.objects
            .only(
                "id", "user_id", "total_amount", "status",
                "duration_months", "period_months", "interest_rate",
                "created_at", "closed_at",
            )
            .filter(user=self.request.user)
        )

    @extend_schema(
        summary="List installments of a plan",
        parameters=[
            OpenApiParameter(
                "ordering", OpenApiParameter.QUERY, OpenApiTypes.STR,
                description="due_date | -due_date (default: due_date)"
            )
        ],
        responses={200: InstallmentSerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="installments")
    def installments(self, request, *args, **kwargs):
        plan_id = kwargs.get("pk")
        ordering = request.query_params.get("ordering") or "due_date"
        if ordering not in {"due_date", "-due_date"}:
            ordering = "due_date"

        qs = (
            Installment.objects
            .select_related("plan", "transaction")
            .only(
                "id",
                "plan_id",
                "due_date",
                "amount",
                "amount_paid",
                "status",
                "paid_at",
                "penalty_amount",
                "transaction_id",
                "note",
                "plan__user_id",
            )
            .filter(plan__id=plan_id, plan__user=request.user)
            .order_by(ordering)
        )
        page = self.paginate_queryset(qs)
        ser = InstallmentSerializer(page or qs, many=True)
        return self.get_paginated_response(
            ser.data
        ) if page is not None else Response(ser.data)
