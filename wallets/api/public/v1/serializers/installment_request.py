# wallets/api/internal/v1/serializers/installment_request.py

from rest_framework import serializers

from merchants.models import MerchantContract
from profiles.models.profile import Profile
from wallets.models import InstallmentRequest
from wallets.services.credit import calculate_installments
from wallets.utils.validators import https_only_validator


class InstallmentRequestCreateSerializer(serializers.Serializer):
    national_id = serializers.CharField(max_length=10)
    amount = serializers.IntegerField(min_value=1)
    return_url = serializers.URLField(
        required=True, validators=[https_only_validator]
    )

    def validate(self, data):
        merchant = self.context["request"].user.merchant
        national_id = data["national_id"]
        amount = data["amount"]

        try:
            contract = MerchantContract.objects.filter(
                merchant=merchant, active=True
            ).latest("created_at")
        except MerchantContract.DoesNotExist:
            raise serializers.ValidationError(
                "قرارداد فعالی برای فروشگاه یافت نشد."
            )

        if amount > contract.max_credit_per_user:
            raise serializers.ValidationError(
                "مبلغ بیش از سقف اعتبار مجاز است."
            )

        try:
            profile = Profile.objects.get(national_id=national_id)
            customer = profile.user.customer
        except Exception:
            raise serializers.ValidationError("مشتری با این کد ملی یافت نشد.")

        data["customer"] = customer
        data["contract"] = contract
        return data


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
