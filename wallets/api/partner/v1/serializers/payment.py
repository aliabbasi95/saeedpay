# wallets/api/partner/v1/serializers/payment.py

from rest_framework import serializers

from wallets.models import PaymentRequest
from wallets.utils.validators import https_only_validator


class PaymentRequestCreateSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)
    return_url = serializers.URLField(
        required=True, validators=[https_only_validator]
    )
    description = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )
    external_guid = serializers.CharField(
        required=False, allow_blank=False, max_length=64
    )
    national_id = serializers.CharField(max_length=10)


class PaymentRequestPartnerDetailSerializer(serializers.ModelSerializer):
    store_id = serializers.IntegerField(source="store.id", read_only=True)
    store_name = serializers.CharField(source="store.name", read_only=True)

    class Meta:
        model = PaymentRequest
        fields = [
            "reference_code",
            "external_guid",
            "amount",
            "description",
            "status",
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


class PaymentVerifyResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    payment_reference_code = serializers.CharField()
    transaction_reference_code = serializers.CharField()
    amount = serializers.IntegerField()


class PaymentRequestCreateResponseSerializer(serializers.Serializer):
    payment_request_id = serializers.IntegerField()
    payment_reference_code = serializers.CharField()
    amount = serializers.IntegerField()
    description = serializers.CharField()
    return_url = serializers.URLField()
    status = serializers.CharField()
    payment_url = serializers.URLField()
