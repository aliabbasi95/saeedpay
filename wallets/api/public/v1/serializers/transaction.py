# wallets/api/public/v1/serializers/transaction.py

from rest_framework import serializers

from wallets.models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    from_wallet = serializers.StringRelatedField()
    to_wallet = serializers.StringRelatedField()

    class Meta:
        model = Transaction
        fields = [
            "id",
            "reference_code",
            "from_wallet",
            "to_wallet",
            "amount",
            "status",
            "description",
            "created_at",
            "updated_at"
        ]
