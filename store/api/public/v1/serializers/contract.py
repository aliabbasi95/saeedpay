# store/api/public/v1/serializers/contract.py

from rest_framework import serializers

from store.models import StoreContract


class StoreContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreContract
        fields = [
            "store",
            "max_credit_per_user",
            "min_credit_per_user",
            "max_repayment_months",
            "min_repayment_months",
            "allowed_period_months",
            "interest_rate",
            "callback_url",
        ]
