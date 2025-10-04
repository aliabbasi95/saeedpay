# credit/api/public/v1/views/credit_limit.py

from rest_framework import mixins, viewsets

from credit.api.public.v1.schema import credit_limit_viewset_schema
from credit.api.public.v1.serializers.credit import CreditLimitSerializer
from credit.models.credit_limit import CreditLimit
from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin


@credit_limit_viewset_schema
class CreditLimitViewSet(
    ScopedThrottleByActionMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    list:     Unpaginated list of user's credit limits (newest first).
    retrieve: Single credit limit owned by the user.
    """
    serializer_class = CreditLimitSerializer
    pagination_class = None
    lookup_field = "pk"

    throttle_scope_map = {
        "default": "credit-limits-read",
        "list": "credit-limits-read",
        "retrieve": "credit-limits-read",
    }

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
