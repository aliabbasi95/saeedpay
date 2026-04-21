# wallets/api/public/v1/views/wallet.py

from rest_framework import mixins, viewsets

from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from wallets.api.public.v1.schema import wallets_list_schema
from wallets.api.public.v1.serializers import (
    WalletListQuerySerializer,
    WalletSerializer,
)
from wallets.models import Wallet


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

    @wallets_list_schema
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
