# wallets/api/internal/v1/serializers/payment_request.py
from rest_framework import serializers


class PaymentRequestCreateSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)
    callback_url = serializers.URLField(required=False, allow_blank=True)
    description = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )
