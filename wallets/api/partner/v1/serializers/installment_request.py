# wallets/api/partner/v1/serializers/installment_request.py

from rest_framework import serializers

from merchants.models import MerchantContract
from profiles.models.profile import Profile
from store.models import StoreContract
from wallets.models import InstallmentRequest
from wallets.utils.validators import https_only_validator


class InstallmentRequestCreateSerializer(serializers.Serializer):
    national_id = serializers.CharField(max_length=10)
    amount = serializers.IntegerField(min_value=1)
    return_url = serializers.URLField(
        required=True, validators=[https_only_validator]
    )

    def validate(self, data):
        store = self.context["request"].store
        national_id = data["national_id"]
        amount = data["amount"]

        try:
            contract = StoreContract.objects.filter(
                store=store, active=True
            ).latest("created_at")
        except StoreContract.DoesNotExist:
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
    class Meta:
        model = InstallmentRequest
        ref_name = "PartnerInstallmentRequestDetail"
        fields = [
            "reference_code",
            "proposal_amount",
            "credit_limit_amount",
            "confirmed_amount",
            "duration_months",
            "period_months",
            "status",
            "user_confirmed_at",
        ]
