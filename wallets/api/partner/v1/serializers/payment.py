# wallets/api/partner/v1/serializers/payment.py

from rest_framework import serializers

from wallets.utils.validators import https_only_validator


class PaymentRequestCreateSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)
    return_url = serializers.URLField(
        required=True, validators=[https_only_validator]
    )
    description = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )


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
