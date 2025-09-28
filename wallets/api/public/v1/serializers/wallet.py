# wallets/api/public/v1/serializers/wallet.py
from django.utils import timezone
from rest_framework import serializers

from wallets.models import Wallet
from wallets.utils.choices import OwnerType, WalletKind


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
    spendable_amount = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = [
            "id",
            "wallet_number",
            "kind",
            "kind_display",
            "owner_type",
            "owner_type_display",
            "spendable_amount",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
        ref_name = "PublicWallet"

    def _get_available_limit(self, obj):
        if obj.kind != WalletKind.CREDIT:
            return 0
        try:
            from credit.models.credit_limit import CreditLimit
            cl = CreditLimit.objects.get_user_credit_limit(obj.user)
        except Exception:
            return 0
        if not cl or not getattr(cl, "is_active", False):
            return 0
        if getattr(
                cl, "expiry_date", None
        ) and cl.expiry_date <= timezone.localdate():
            return 0
        return int(getattr(cl, "available_limit", 0) or 0)

    def get_spendable_amount(self, obj) -> int:
        # Always non-negative, what UI should display as spendable capacity
        if obj.kind == WalletKind.CREDIT:
            return self._get_available_limit(obj)
        return max(0, int(getattr(obj, "available_balance", 0) or 0))
