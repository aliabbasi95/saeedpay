# store/api/public/v1/serializers/apikey.py

from rest_framework import serializers


class StoreApiKeyRegenerateResponseSerializer(serializers.Serializer):
    api_key = serializers.CharField()
