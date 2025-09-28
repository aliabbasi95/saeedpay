# wallets/api/public/v1/serializers/payment.py
import re

from django.utils import timezone
from rest_framework import serializers

from auth_api.models import PhoneOTP
from wallets.api.public.v1.serializers import WalletSerializer
from wallets.models import PaymentRequest, Wallet
from wallets.utils.choices import WalletKind, OwnerType


class PaymentRequestDetailSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(
        source='store.name', read_only=True
    )
    store_id = serializers.IntegerField(
        source='store.id', read_only=True
    )
    status = serializers.CharField(read_only=True)

    class Meta:
        model = PaymentRequest
        fields = [
            "reference_code",
            "amount",
            "description",
            "store_id",
            "store_name",
            "status",
            "expires_at",
        ]


class PaymentConfirmSerializer(serializers.Serializer):
    wallet_id = serializers.IntegerField()
    code = serializers.CharField()

    def validate(self, data):
        user = self.context["request"].user
        phone_number = user.profile.phone_number

        if not phone_number or not re.match(r'^09\d{9}$', phone_number):
            raise serializers.ValidationError(
                {"phone_number": ["شماره تلفن معتبر نیست."]}
            )

        code = data.get("code")
        try:
            otp_instance = PhoneOTP.objects.get(phone_number=phone_number)
        except PhoneOTP.DoesNotExist:
            raise serializers.ValidationError(
                {"code": "کد تایید یافت نشد یا منقضی شده است."}
            )

        if not otp_instance.verify(code):
            raise serializers.ValidationError(
                {"code": "کد تایید اشتباه یا منقضی شده است."}
            )

        return data


class PaymentConfirmResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    payment_reference_code = serializers.CharField()
    transaction_reference_code = serializers.CharField()
    return_url = serializers.URLField()


class PaymentRequestDetailWithWalletsSerializer(
    PaymentRequestDetailSerializer
):
    def _can_wallet_pay_full(self, wallet, amount: int) -> bool:
        if wallet.kind == WalletKind.CREDIT:
            try:
                from credit.models.credit_limit import CreditLimit
                cl = CreditLimit.objects.get_user_credit_limit(wallet.user)
            except Exception:
                return False
            if not cl or not getattr(cl, "is_active", False):
                return False
            if getattr(
                    cl, "expiry_date", None
            ) and cl.expiry_date <= timezone.localdate():
                return False
            return int(getattr(cl, "available_limit", 0) or 0) >= int(amount)
        return int(getattr(wallet, "available_balance", 0) or 0) >= int(amount)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            wallets_qs = Wallet.objects.filter(
                user=user, owner_type=OwnerType.CUSTOMER
            )
            eligible = [w for w in wallets_qs if
                        self._can_wallet_pay_full(w, instance.amount)]
            data["available_wallets"] = WalletSerializer(
                eligible, many=True
            ).data
        return data

    class Meta(PaymentRequestDetailSerializer.Meta):
        fields = PaymentRequestDetailSerializer.Meta.fields
