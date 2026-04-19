# wallets/api/public/v1/views/wallet.py
# Read-only ViewSet for user's wallets with validated owner_type filter.

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import mixins, viewsets

from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from wallets.api.public.v1.serializers import (
    WalletListQuerySerializer,
    WalletSerializer,
)
from wallets.models import Wallet


@extend_schema(
    tags=["Wallet · Wallets"],
    summary="List user's wallets",
    description="Returns the authenticated user's wallets. Optional filter by owner_type.",
    parameters=[
        OpenApiParameter(
            name="owner_type",
            location=OpenApiParameter.QUERY,
            required=True,
            description="Filter by owner_type (e.g. customer, merchant)",
            type=OpenApiTypes.STR,
        )
    ],
)
class WalletViewSet(
    ScopedThrottleByActionMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    list: Paginated list of the current user's wallets.
    """

    serializer_class = WalletSerializer

    throttle_scope_map = {
        "default": "wallets-read",
        "list": "wallets-read",
    }

    def list(self, request, *args, **kwargs):
        query_serializer = WalletListQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        query_serializer = WalletListQuerySerializer(data=self.request.query_params)
        query_serializer.is_valid(raise_exception=True)

        owner_type = query_serializer.validated_data["owner_type"]

        return (
            Wallet.objects.only(
                "id",
                "wallet_number",
                "kind",
                "owner_type",
                "balance",
                "reserved_balance",
                "user_id",
                "created_at",
                "updated_at",
            )
            .filter(user=self.request.user, owner_type=owner_type)
            .order_by("kind", "id")
        )
