# wallets/api/public/v1/serializers/installment_request.py

from rest_framework import serializers

from wallets.models import InstallmentRequest
from wallets.services.credit import calculate_installments


class InstallmentRequestDetailSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(
        source="merchant.shop_name",
        read_only=True
    )
    status = serializers.CharField(
        source="get_status_display",
        read_only=True
    )

    class Meta:
        model = InstallmentRequest
        fields = [
            "reference_code",
            "merchant_name",
            "credit_limit_amount",
            "status",
            "return_url"
        ]


class InstallmentRequestConfirmSerializer(serializers.Serializer):
    confirmed_amount = serializers.IntegerField(min_value=1)
    duration_months = serializers.IntegerField(min_value=1)
    period_months = serializers.IntegerField(min_value=1)

    def validate(self, data):
        request_obj = self.context["installment_request"]

        if request_obj.status != "created":
            raise serializers.ValidationError(
                "این درخواست قبلاً تایید شده است."
            )

        if data["confirmed_amount"] > request_obj.credit_limit_amount:
            raise serializers.ValidationError(
                "مقدار انتخاب‌شده بیش از سقف اعتبار مجاز است."
            )

        allowed_periods = request_obj.contract.allowed_period_months
        if data["period_months"] not in allowed_periods:
            raise serializers.ValidationError("پریود انتخابی نامعتبر است.")

        if data["duration_months"] > request_obj.contract.max_repayment_months:
            raise serializers.ValidationError(
                "مدت بازپرداخت بیش از حد مجاز است."
            )

        data["installment_plan"] = calculate_installments(
            data["confirmed_amount"],
            data["duration_months"],
            data["period_months"],
            request_obj.contract.interest_rate,
        )
        return data
