# wallets/api/public/v1/views/wallet.py
# Read-only ViewSet for user's wallets with optional owner_type filter.

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework import viewsets, mixins

from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from wallets.api.public.v1.serializers import WalletSerializer
from wallets.models import Wallet


@extend_schema(
    tags=["Wallet · Wallets"],
    summary="List user's wallets",
    description="Returns the authenticated user's wallets. Optional filter by owner_type.",
    parameters=[
        OpenApiParameter(
            name="owner_type",
            location=OpenApiParameter.QUERY,
            required=False,
            description="Filter by owner_type (e.g. customer, merchant)",
            type=OpenApiTypes.STR,
        )
    ],
)
class WalletViewSet(
    ScopedThrottleByActionMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet
):
    """
    list: Paginated list of the current user's wallets.
    """
    serializer_class = WalletSerializer

    throttle_scope_map = {
        "default": "wallets-read",
        "list": "wallets-read",
    }

    def get_queryset(self):
        owner_type = self.request.query_params.get("owner_type") or None
        qs = (
            Wallet.objects
            .only(
                "id", "wallet_number", "kind", "owner_type",
                "balance", "reserved_balance", "user_id",
                "created_at", "updated_at",
            )
            .filter(user=self.request.user)
            .order_by("kind", "id")
        )
        if owner_type:
            qs = qs.filter(owner_type=owner_type)
        return qs
