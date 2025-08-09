# wallets/api/partner/v1/serializers/installment_request.py

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from store.models import StoreContract
from wallets.api.public.v1.serializers import InstallmentSerializer
from wallets.models import InstallmentRequest
from wallets.utils.choices import (
    InstallmentRequestStatus,
)


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


class InstallmentRequestDetailSerializer(serializers.ModelSerializer):
    installments = serializers.SerializerMethodField()

    @extend_schema_field(
        serializers.ListField(child=InstallmentSerializer())
    )
    def get_installments(self, obj):
        if obj.status != InstallmentRequestStatus.COMPLETED:
            return None
        plan = obj.get_installment_plan()
        if not plan:
            return None
        installments = plan.installments.order_by("due_date")
        return InstallmentSerializer(installments, many=True).data

    class Meta:
        model = InstallmentRequest
        ref_name = "PartnerInstallmentRequestDetail"
        fields = [
            "reference_code",
            "proposal_amount",
            "confirmed_amount",
            "duration_months",
            "period_months",
            "status",
            "user_confirmed_at",
            "installments",
        ]


class InstallmentRequestVerifyResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    reference_code = serializers.CharField()
    confirmed_amount = serializers.IntegerField()
    duration_months = serializers.IntegerField()
    period_months = serializers.IntegerField()
