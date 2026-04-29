# banking/api/public/v1/serializers/bank.py

from rest_framework import serializers

from banking.models import Bank


class BankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bank
        fields = [
            "id",
            "name",
            "logo",
            "color",
        ]


class BankDetailSerializer(BankSerializer):
    class Meta(BankSerializer.Meta):
        fields = BankSerializer.Meta.fields + [
            "created_at",
            "updated_at",
        ]
