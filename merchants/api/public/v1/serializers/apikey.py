from rest_framework import serializers

class MerchantApiKeyRegenerateResponseSerializer(serializers.Serializer):
    api_key = serializers.CharField()
