# wallets/api/partner/v1/serializers/payment.py

from rest_framework import serializers

from wallets.models import PaymentRequest
from wallets.utils.choices import PaymentFlowType
from wallets.utils.validators import https_only_validator


class PaymentRequestCreateSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)
    return_url = serializers.URLField(
        required=True,
        validators=[https_only_validator],
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
    )
    external_guid = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=64,
    )
    national_id = serializers.CharField(max_length=10)
    flow_type = serializers.ChoiceField(
        choices=PaymentFlowType.choices,
        required=False,
        default=PaymentFlowType.ONLINE,
    )


class PaymentRequestPartnerDetailSerializer(serializers.ModelSerializer):
    store_id = serializers.IntegerField(source="store.id", read_only=True)
    store_name = serializers.CharField(source="store.name", read_only=True)
    flow_type_display = serializers.CharField(
        source="get_flow_type_display",
        read_only=True,
    )
    merchant_confirmation_required = serializers.SerializerMethodField()

    class Meta:
        model = PaymentRequest
        fields = [
            "reference_code",
            "external_guid",
            "amount",
            "description",
            "status",
            "flow_type",
            "flow_type_display",
            "merchant_confirmation_required",
            "expires_at",
            "paid_at",
            "paid_by",
            "paid_wallet",
            "store_id",
            "store_name",
            "return_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_merchant_confirmation_required(self, obj):
        return obj.flow_type == PaymentFlowType.ONLINE


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


class PaymentVerifyResponseSerializer(PaymentActionResponseSerializer):
    """
    Backward-compatible alias for older imports/schemas.
    """
    pass


class PaymentRequestCreateResponseSerializer(serializers.Serializer):
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
    payment_request_id = serializers.IntegerField()
    flow_type = serializers.CharField()
    payment_url = serializers.URLField()
