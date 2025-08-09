# wallets/api/public/v1/serializers/wallet.py
from rest_framework import serializers

from wallets.models import Wallet
from wallets.utils.choices import OwnerType


class WalletListQuerySerializer(serializers.Serializer):
    owner_type = serializers.ChoiceField(
        choices=OwnerType.choices,
        required=True,
        label="نوع مالک",
    )


class WalletSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(
        source="get_kind_display", read_only=True
    )
    owner_type_display = serializers.CharField(
        source="get_owner_type_display", read_only=True
    )
    available_balance = serializers.ReadOnlyField()

    def get_available_balance(self, obj):
        return obj.balance - obj.reserved_balance

    class Meta:
        model = Wallet
        fields = [
            "id",
            "wallet_number",
            "kind",
            "kind_display",
            "owner_type",
            "owner_type_display",
            "balance",
            "available_balance",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
        ref_name = "PublicWallet"
