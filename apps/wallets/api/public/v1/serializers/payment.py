# apps/wallets/api/public/v1/serializers/payment.py

import re

from django.utils import timezone
from drf_spectacular.utils import OpenApiTypes, extend_schema_field
from rest_framework import serializers

from apps.auth_api.models import PhoneOTP
from apps.wallets.api.public.v1.serializers.wallet import WalletSerializer
from apps.wallets.models import PaymentRequest
from apps.wallets.services.payment import list_eligible_wallets_for_payment_request
from apps.wallets.utils.choices import PaymentFlowType, PaymentRequestStatus


class PaymentRequestDetailSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source="store.name", read_only=True)
    store_id = serializers.IntegerField(source="store.id", read_only=True)
    status = serializers.CharField(read_only=True)
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    flow_type = serializers.CharField(read_only=True)
    flow_type_display = serializers.CharField(
        source="get_flow_type_display",
        read_only=True,
    )
    merchant_confirmation_required = serializers.SerializerMethodField()

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
            "flow_type",
            "flow_type_display",
            "merchant_confirmation_required",
            "expires_at",
            "paid_at",
        ]
        read_only_fields = fields

    def get_merchant_confirmation_required(self, obj: PaymentRequest) -> bool:
        return obj.flow_type == PaymentFlowType.ONLINE


class PaymentConfirmSerializer(serializers.Serializer):
    wallet_id = serializers.IntegerField(min_value=1)
    code = serializers.CharField(min_length=4, max_length=10)

    def validate(self, data):
        user = self.context["request"].user
        phone_number = getattr(
            getattr(user, "profile", None),
            "phone_number",
            None,
        )

        if not phone_number or not re.match(r"^09\d{9}$", phone_number):
            raise serializers.ValidationError(
                {"phone_number": ["شماره تلفن معتبر نیست."]}
            )

        try:
            otp_instance = PhoneOTP.objects.get(phone_number=phone_number)
        except PhoneOTP.DoesNotExist as exc:
            raise serializers.ValidationError(
                {"code": "کد تایید یافت نشد یا منقضی شده است."}
            ) from exc

        if not otp_instance.verify(data.get("code")):
            raise serializers.ValidationError(
                {"code": "کد تایید اشتباه یا منقضی شده است."}
            )

        return data


class PaymentActionResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField()
    payment_reference_code = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    payment_request_status = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    payment_status = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    transaction_reference_code = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    next_action = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    merchant_confirmation_required = serializers.BooleanField(
        required=False,
        allow_null=True,
    )
    return_url = serializers.URLField(
        required=False,
        allow_null=True,
    )
    amount = serializers.IntegerField(
        required=False,
        allow_null=True,
    )


class PaymentConfirmResponseSerializer(PaymentActionResponseSerializer):
    """
    Backward-compatible alias for older imports/schemas.
    """

    pass


class PaymentRequestDetailWithWalletsSerializer(PaymentRequestDetailSerializer):
    available_wallets = serializers.SerializerMethodField()
    can_pay = serializers.SerializerMethodField()
    reason = serializers.SerializerMethodField()

    def _get_request_user(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def _is_authenticated(self, user):
        return bool(user and user.is_authenticated)

    def _is_payer_allowed(self, obj: PaymentRequest, user) -> bool:
        if not self._is_authenticated(user):
            return False

        if not obj.customer_id:
            return True

        user_customer = getattr(user, "customer", None)
        return bool(user_customer and user_customer.id == obj.customer_id)

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_available_wallets(self, obj: PaymentRequest):
        user = self._get_request_user()
        if not self._is_payer_allowed(obj, user):
            return []

        qs = list_eligible_wallets_for_payment_request(user, obj)
        return WalletSerializer(qs, many=True).data

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_pay(self, obj: PaymentRequest) -> bool:
        user = self._get_request_user()

        if obj.status != PaymentRequestStatus.CREATED:
            return False

        if obj.expires_at and obj.expires_at < timezone.localtime(timezone.now()):
            return False

        if not self._is_authenticated(user):
            return False

        return self._is_payer_allowed(obj, user)

    @extend_schema_field(OpenApiTypes.STR)
    def get_reason(self, obj: PaymentRequest):
        user = self._get_request_user()

        if obj.status == PaymentRequestStatus.EXPIRED:
            return "expired"

        if obj.status != PaymentRequestStatus.CREATED:
            return "not_payable"

        if obj.expires_at and obj.expires_at < timezone.localtime(timezone.now()):
            return "expired"

        if not self._is_authenticated(user):
            return "authentication_required"

        if obj.customer_id:
            user_customer = getattr(user, "customer", None)
            if not user_customer or user_customer.id != obj.customer_id:
                return "not_allowed"

        return None

    class Meta(PaymentRequestDetailSerializer.Meta):
        fields = PaymentRequestDetailSerializer.Meta.fields + [
            "available_wallets",
            "can_pay",
            "reason",
        ]
        read_only_fields = fields


class PaymentRequestListItemSerializer(PaymentRequestDetailSerializer):
    created_at = serializers.DateTimeField(read_only=True)

    class Meta(PaymentRequestDetailSerializer.Meta):
        fields = PaymentRequestDetailSerializer.Meta.fields + ["created_at"]
        read_only_fields = fields
