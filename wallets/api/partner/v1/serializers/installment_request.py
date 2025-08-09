# wallets/api/partner/v1/serializers/installment_request.py

from rest_framework import serializers

from store.models import StoreContract


class InstallmentRequestCreateSerializer(serializers.Serializer):
    national_id = serializers.CharField(max_length=10)
    amount = serializers.IntegerField(min_value=1)
    guid = serializers.CharField(max_length=64)

    def validate(self, data):
        store = self.context["request"].store
        amount = data["amount"]

        try:
            contract = StoreContract.objects.filter(
                store=store, active=True
            ).latest("created_at")
        except StoreContract.DoesNotExist:
            raise serializers.ValidationError(
                "قرارداد فعالی برای فروشگاه یافت نشد."
            )

        data["amount"] = min(amount, contract.max_credit_per_user)
        data["contract"] = contract
        return data


class InstallmentRequestVerifyResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    reference_code = serializers.CharField()
    confirmed_amount = serializers.IntegerField()
    duration_months = serializers.IntegerField()
    period_months = serializers.IntegerField()
