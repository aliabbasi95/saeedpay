# auth_api/api/public/v1/serializers/logout.py
from rest_framework import serializers


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
