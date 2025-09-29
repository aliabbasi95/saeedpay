# wallets/api/public/v1/views/installment.py
# Read-only ViewSet for user's installments with filters.

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework import viewsets, mixins

from wallets.api.public.v1.serializers import InstallmentSerializer
from wallets.models import Installment


@extend_schema(
    tags=["Wallet · Installments"],
    summary="List/Retrieve user's installments",
    description="Returns all installments of the user with optional status and due_date range filters.",
    parameters=[
        OpenApiParameter(
            "status", OpenApiParameter.QUERY, OpenApiTypes.STR,
            description="Filter by status (e.g. unpaid, paid)"
        ),
        OpenApiParameter(
            "due_from", OpenApiParameter.QUERY, OpenApiTypes.DATE,
            description="Include items with due_date >= this date (YYYY-MM-DD)"
        ),
        OpenApiParameter(
            "due_to", OpenApiParameter.QUERY, OpenApiTypes.DATE,
            description="Include items with due_date <= this date (YYYY-MM-DD)"
        ),
        OpenApiParameter(
            "ordering", OpenApiParameter.QUERY, OpenApiTypes.STR,
            description="One of: due_date, -due_date (default: due_date)"
        )
    ]
)
class InstallmentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    """
    list:     Paginated list of all user's installments (across plans).
    retrieve: Single installment details (owned by the user).
    """
    serializer_class = InstallmentSerializer
    lookup_field = "pk"

    def get_queryset(self):
        params = self.request.query_params
        ordering = params.get("ordering") or "due_date"
        if ordering not in {"due_date", "-due_date"}:
            ordering = "due_date"

        qs = (
            Installment.objects
            .select_related("plan", "transaction")
            .only(
                "id", "plan_id", "due_date", "amount", "amount_paid",
                "status", "paid_at", "penalty_amount", "transaction_id",
                "note",
                "plan__user_id",
            )
            .filter(plan__user=self.request.user)
        )

        status_param = params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        due_from = params.get("due_from")
        if due_from:
            qs = qs.filter(due_date__gte=due_from)

        due_to = params.get("due_to")
        if due_to:
            qs = qs.filter(due_date__lte=due_to)

        return qs.order_by(ordering)
