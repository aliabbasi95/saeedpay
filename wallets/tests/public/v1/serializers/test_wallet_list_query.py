# wallets/tests/public/v1/serializers/test_wallet_list_query.py

from wallets.api.public.v1.serializers.wallet import WalletListQuerySerializer
from wallets.utils.choices import OwnerType


class TestWalletListQuerySerializer:

    def test_valid_owner_type(self):
        serializer = WalletListQuerySerializer(
            data={"owner_type": OwnerType.CUSTOMER}
        )
        assert serializer.is_valid()
        assert serializer.validated_data["owner_type"] == OwnerType.CUSTOMER

    def test_missing_owner_type(self):
        serializer = WalletListQuerySerializer(data={})
        assert not serializer.is_valid()
        assert "owner_type" in serializer.errors

    def test_invalid_owner_type(self):
        serializer = WalletListQuerySerializer(data={"owner_type": "INVALID"})
        assert not serializer.is_valid()
        assert "owner_type" in serializer.errors

    def test_owner_type_null(self):
        serializer = WalletListQuerySerializer(data={"owner_type": None})
        assert not serializer.is_valid()
        assert "owner_type" in serializer.errors
