# wallets/api/public/v1/serializers/wallet.py
from rest_framework import serializers

from wallets.models import Wallet


class WalletSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(
        source="get_kind_display", read_only=True
        )
    owner_type_display = serializers.CharField(
        source="get_owner_type_display", read_only=True
        )

    class Meta:
        model = Wallet
        fields = [
            "id",
            "kind",
            "kind_display",
            "owner_type",
            "owner_type_display",
            "balance",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
