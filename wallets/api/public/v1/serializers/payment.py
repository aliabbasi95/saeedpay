# wallets/api/public/v1/serializers/payment.py

import re

from django.utils import timezone
from rest_framework import serializers

from auth_api.models import PhoneOTP
from wallets.api.public.v1.serializers import WalletSerializer
from wallets.models import PaymentRequest, Wallet
from wallets.utils.choices import OwnerType, PaymentRequestStatus


class PaymentRequestDetailSerializer(serializers.ModelSerializer):
    """
    Base detail for a single payment request (no wallet list).
    """
    store_name = serializers.CharField(source="store.name", read_only=True)
    store_id = serializers.IntegerField(source="store.id", read_only=True)
    status = serializers.CharField(read_only=True)
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )

    class Meta:
        model = PaymentRequest
        fields = [
            "reference_code",
            "amount",
            "description",
            "store_id",
            "store_name",
            "status",
            "status_display",
            "expires_at",
            "paid_at",
        ]
        read_only_fields = fields


class PaymentConfirmSerializer(serializers.Serializer):
    """
    Payload for confirming a payment request.
    """
    wallet_id = serializers.IntegerField(min_value=1)
    code = serializers.CharField(min_length=4, max_length=10)

    def validate(self, data):
        """
        Validate OTP code for the authenticated user's phone number.
        """
        user = self.context["request"].user
        phone_number = getattr(
            getattr(user, "profile", None), "phone_number", None
        )

        if not phone_number or not re.match(r"^09\d{9}$", phone_number):
            raise serializers.ValidationError(
                {"phone_number": ["شماره تلفن معتبر نیست."]}
            )

        try:
            otp_instance = PhoneOTP.objects.get(phone_number=phone_number)
        except PhoneOTP.DoesNotExist:
            raise serializers.ValidationError(
                {"code": "کد تایید یافت نشد یا منقضی شده است."}
            )

        if not otp_instance.verify(data.get("code")):
            raise serializers.ValidationError(
                {"code": "کد تایید اشتباه یا منقضی شده است."}
            )

        return data


class PaymentConfirmResponseSerializer(serializers.Serializer):
    """
    Response returned after a successful confirm.
    """
    detail = serializers.CharField()
    payment_reference_code = serializers.CharField()
    transaction_reference_code = serializers.CharField(
        allow_blank=True, required=False
        )
    return_url = serializers.URLField()


class PaymentRequestDetailWithWalletsSerializer(
    PaymentRequestDetailSerializer
):
    """
    Detail serializer extended with user's available wallets and convenience flags.
    - available_wallets: only when user is authenticated
    - can_pay: True only when status is CREATED and not expired yet
    - reason: 'expired' when status is EXPIRED (helps clients to branch UI)
    """
    available_wallets = serializers.SerializerMethodField()
    can_pay = serializers.SerializerMethodField()
    reason = serializers.SerializerMethodField()

    def get_available_wallets(self, obj: PaymentRequest):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            qs = Wallet.objects.filter(
                user=user, owner_type=OwnerType.CUSTOMER
            )
            return WalletSerializer(qs, many=True).data
        return []

    def get_can_pay(self, obj: PaymentRequest) -> bool:
        # Payment allowed only when PR is in CREATED and not yet expired.
        if obj.status != PaymentRequestStatus.CREATED:
            return False
        if obj.expires_at and obj.expires_at < timezone.now():
            return False
        return True

    def get_reason(self, obj: PaymentRequest):
        if obj.status == PaymentRequestStatus.EXPIRED:
            return "expired"
        return None

    class Meta(PaymentRequestDetailSerializer.Meta):
        fields = PaymentRequestDetailSerializer.Meta.fields + [
            "available_wallets",
            "can_pay",
            "reason",
        ]
        read_only_fields = fields


class PaymentRequestListItemSerializer(PaymentRequestDetailSerializer):
    """
    List item view; adds `created_at` for sorting/context.
    """
    created_at = serializers.DateTimeField(read_only=True)

    class Meta(PaymentRequestDetailSerializer.Meta):
        fields = PaymentRequestDetailSerializer.Meta.fields + ["created_at"]
        read_only_fields = fields
