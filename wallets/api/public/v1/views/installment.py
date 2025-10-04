# wallets/api/public/v1/views/installment.py
# Read-only ViewSet for user's installments with filters.

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, mixins
from rest_framework.filters import OrderingFilter

from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from wallets.api.public.v1.schema import installments_schema
from wallets.api.public.v1.serializers import InstallmentSerializer
from wallets.filters import InstallmentFilter
from wallets.models import Installment


@installments_schema
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
    lookup_value_regex = r"\d+"

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
        if getattr(self, "swagger_fake_view", False):
            return Installment.objects.none()
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
