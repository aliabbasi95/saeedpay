# credit/api/public/v1/views/credit_limit.py
# Read-only ViewSet for user's credit limits.

from rest_framework import mixins, viewsets
from drf_spectacular.utils import extend_schema
from credit.models.credit_limit import CreditLimit
from credit.api.public.v1.serializers.credit import CreditLimitSerializer


@extend_schema(tags=["Credit Limits"])
class CreditLimitViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
    ):
    """
    list:     Unpaginated list of user's credit limits (newest first).
    retrieve: Single credit limit owned by the user.
    """
    serializer_class = CreditLimitSerializer
    pagination_class = None
    lookup_field = "pk"

    def get_queryset(self):
        return (
            CreditLimit.objects
            .only(
                "id", "user_id", "approved_limit", "is_active",
                "grace_period_days", "expiry_date",
                "created_at", "updated_at", "reference_code",
            )
            .filter(user=self.request.user)
            .order_by("-created_at")
        )
