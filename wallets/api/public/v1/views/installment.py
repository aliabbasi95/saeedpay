# wallets/api/public/v1/views/installment.py
# Read-only ViewSet for user's installments with filters.

# wallets/api/public/v1/views/installment.py

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework import viewsets, mixins
from rest_framework.filters import OrderingFilter

from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from wallets.api.public.v1.serializers import InstallmentSerializer
from wallets.filters import InstallmentFilter
from wallets.models import Installment


@extend_schema(
    tags=["Wallet · Installments"],
    summary="List/Retrieve user's installments",
    description="Returns all installments of the user with filters and ordering.",
    parameters=[
        OpenApiParameter(
            "status", OpenApiParameter.QUERY, OpenApiTypes.STR,
            description="unpaid | paid | ..."
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
            description="due_date | -due_date (default: due_date)"
        ),
    ],
)
class InstallmentViewSet(
    ScopedThrottleByActionMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    list:     Paginated list of all user's installments (across plans).
    retrieve: Single installment details (owned by the user).
    """
    serializer_class = InstallmentSerializer
    lookup_field = "pk"

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = InstallmentFilter
    ordering_fields = ["due_date"]
    ordering = ["due_date"]

    throttle_scope_map = {
        "default": "installments-read",
        "list": "installments-read",
        "retrieve": "installments-read",
    }

    def get_queryset(self):
        return (
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
            .filter(plan__user=self.request.user)
        )
