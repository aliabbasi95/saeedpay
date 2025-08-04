# wallets/api/public/v1/serializers/installment_plan.py

from rest_framework import serializers
from wallets.models import InstallmentPlan


class InstallmentPlanSerializer(serializers.ModelSerializer):
    total_installments = serializers.IntegerField(source="installments.count", read_only=True)

    class Meta:
        model = InstallmentPlan
        fields = [
            "id",
            "total_amount",
            "status",
            "duration_months",
            "period_months",
            "interest_rate",
            "created_at",
            "closed_at",
            "total_installments"
        ]
