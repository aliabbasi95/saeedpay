from rest_framework import serializers

class PaymentConfirmSerializer(serializers.Serializer):
    payment_request_id = serializers.IntegerField()
    wallet_id = serializers.IntegerField()
