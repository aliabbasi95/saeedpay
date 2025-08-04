# wallets/api/public/v1/serializers/installment.py

from rest_framework import serializers

from wallets.models import Installment


class InstallmentSerializer(serializers.ModelSerializer):
    is_overdue = serializers.BooleanField(read_only=True)
    current_penalty = serializers.SerializerMethodField()
    total_due = serializers.SerializerMethodField()

    def get_current_penalty(self, obj: Installment) -> int:
        return obj.calculate_penalty()

    def get_total_due(self, obj: Installment) -> int:
        return obj.amount + obj.calculate_penalty()

    class Meta:
        model = Installment
        fields = [
            "id",
            "due_date",
            "amount",
            "amount_paid",
            "status",
            "paid_at",
            "transaction_id",
            "is_overdue",
            "current_penalty",
            "penalty_amount",
            "total_due",
            "note"
        ]
