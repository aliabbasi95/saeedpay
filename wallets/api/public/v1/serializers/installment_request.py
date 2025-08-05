# wallets/api/public/v1/serializers/installment_request.py

from rest_framework import serializers

from wallets.models import InstallmentRequest
from wallets.services import calculate_installments
from wallets.utils.choices import InstallmentRequestStatus


class InstallmentRequestDetailSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(
        source="store.name",
        read_only=True
    )
    status = serializers.CharField(
        source="get_status_display",
        read_only=True
    )

    min_credit = serializers.IntegerField(
        source="contract.min_credit_per_user",
        read_only=True
    )
    max_credit = serializers.IntegerField(
        source="contract.max_credit_per_user",
        read_only=True
    )
    min_repayment_months = serializers.IntegerField(
        source="contract.min_repayment_months",
        read_only=True
    )
    max_repayment_months = serializers.IntegerField(
        source="contract.max_repayment_months",
        read_only=True
    )
    allowed_periods = serializers.ListField(
        source="contract.allowed_period_months",
        read_only=True
    )
    interest_rate = serializers.FloatField(
        source="contract.interest_rate",
        read_only=True
    )

    class Meta:
        model = InstallmentRequest
        ref_name = "PublicInstallmentRequestDetail"
        fields = [
            "reference_code",
            "store_name",
            "credit_limit_amount",
            "status",
            "return_url",
            "min_credit",
            "max_credit",
            "min_repayment_months",
            "max_repayment_months",
            "allowed_periods",
            "interest_rate",
        ]


class InstallmentRequestConfirmSerializer(serializers.Serializer):
    confirmed_amount = serializers.IntegerField(min_value=1)
    duration_months = serializers.IntegerField(min_value=1)
    period_months = serializers.IntegerField(min_value=1)

    def validate(self, data):
        request_obj = self.context["installment_request"]
        contract = request_obj.contract

        if request_obj.status != InstallmentRequestStatus.CREATED:
            raise serializers.ValidationError(
                "این درخواست قبلاً تایید شده است."
            )

        if data["confirmed_amount"] > request_obj.credit_limit_amount:
            raise serializers.ValidationError(
                "مقدار انتخاب‌شده بیش از سقف اعتبار مجاز است."
            )

        if data["confirmed_amount"] < contract.min_credit_per_user:
            raise serializers.ValidationError(
                "مقدار انتخاب‌شده کمتر از حداقل اعتبار مجاز است."
            )

        if data["duration_months"] > contract.max_repayment_months:
            raise serializers.ValidationError(
                "مدت بازپرداخت بیش از حد مجاز است."
            )

        if data["duration_months"] < contract.min_repayment_months:
            raise serializers.ValidationError(
                "مدت بازپرداخت کمتر از حداقل مجاز است."
            )

        if data["period_months"] > data["duration_months"]:
            raise serializers.ValidationError(
                "پریود بازپرداخت نمی‌تواند بزرگ‌تر از مدت بازپرداخت باشد."
            )

        if data["period_months"] not in contract.allowed_period_months:
            raise serializers.ValidationError("پریود انتخابی نامعتبر است.")

        data["installment_plan"] = calculate_installments(
            data["confirmed_amount"],
            data["duration_months"],
            data["period_months"],
            request_obj.contract.interest_rate,
        )
        return data
