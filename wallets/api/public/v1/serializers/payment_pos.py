# wallets/api/public/v1/serializers/payment_pos.py

from django.utils import timezone
from rest_framework import serializers

from wallets.models import PaymentRequest
from wallets.utils.choices import PaymentFlowType, PaymentRequestStatus


class MerchantPosPaymentRequestCreateSerializer(serializers.Serializer):
    store_id = serializers.IntegerField(min_value=1)
    amount = serializers.IntegerField(min_value=1)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
    )


class MerchantPosPaymentRequestBaseSerializer(serializers.ModelSerializer):
    store_id = serializers.IntegerField(source="store.id", read_only=True)
    store_name = serializers.CharField(source="store.name", read_only=True)
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    flow_type_display = serializers.CharField(
        source="get_flow_type_display",
        read_only=True,
    )
    merchant_confirmation_required = serializers.SerializerMethodField()
    qr_payload = serializers.CharField(source="reference_code", read_only=True)
    can_cancel = serializers.SerializerMethodField()
    can_recreate = serializers.SerializerMethodField()
    status_action_hint = serializers.SerializerMethodField()
    is_paid = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = PaymentRequest
        fields = [
            "reference_code",
            "qr_payload",
            "amount",
            "description",
            "status",
            "status_display",
            "flow_type",
            "flow_type_display",
            "merchant_confirmation_required",
            "can_cancel",
            "can_recreate",
            "status_action_hint",
            "is_paid",
            "is_expired",
            "expires_at",
            "paid_at",
            "store_id",
            "store_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_merchant_confirmation_required(self, obj):
        return obj.flow_type == PaymentFlowType.ONLINE

    def get_can_cancel(self, obj):
        return (
                obj.flow_type == PaymentFlowType.QR_POS
                and obj.status == PaymentRequestStatus.CREATED
        )

    def get_can_recreate(self, obj):
        return (
                obj.flow_type == PaymentFlowType.QR_POS
                and obj.status in {
                    PaymentRequestStatus.COMPLETED,
                    PaymentRequestStatus.CANCELLED,
                    PaymentRequestStatus.EXPIRED,
                }
        )

    def get_status_action_hint(self, obj):
        if obj.flow_type != PaymentFlowType.QR_POS:
            return None

        if obj.status == PaymentRequestStatus.CREATED:
            return "waiting_for_customer_scan"

        if obj.status == PaymentRequestStatus.COMPLETED:
            return "create_new_qr"

        if obj.status == PaymentRequestStatus.CANCELLED:
            return "create_new_qr"

        if obj.status == PaymentRequestStatus.EXPIRED:
            return "create_new_qr"

        if obj.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION:
            return "awaiting_store_confirmation"

        return None

    def get_is_paid(self, obj):
        return obj.status == PaymentRequestStatus.COMPLETED

    def get_is_expired(self, obj):
        if obj.status == PaymentRequestStatus.EXPIRED:
            return True

        if obj.expires_at is None:
            return False

        return obj.expires_at < timezone.localtime(timezone.now())


class MerchantPosPaymentRequestListItemSerializer(
    MerchantPosPaymentRequestBaseSerializer
):
    class Meta(MerchantPosPaymentRequestBaseSerializer.Meta):
        fields = [
            "reference_code",
            "qr_payload",
            "amount",
            "description",
            "status",
            "status_display",
            "flow_type",
            "flow_type_display",
            "merchant_confirmation_required",
            "can_cancel",
            "can_recreate",
            "status_action_hint",
            "is_paid",
            "is_expired",
            "expires_at",
            "paid_at",
            "store_id",
            "store_name",
            "created_at",
        ]
        read_only_fields = fields


class MerchantPosPaymentRequestDetailSerializer(
    MerchantPosPaymentRequestBaseSerializer
):
    pass


class MerchantPosPaymentRequestCreateResponseSerializer(serializers.Serializer):
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
    amount = serializers.IntegerField(
        required=False,
        allow_null=True,
    )
    payment_request_id = serializers.IntegerField()
    flow_type = serializers.CharField()
    payment_url = serializers.URLField()
    qr_payload = serializers.CharField()
    store_id = serializers.IntegerField()
    store_name = serializers.CharField()
