# auth_api/api/public/v1/serializers/logout.py
from rest_framework import serializers


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate_refresh(self, value):
        if not isinstance(value, str):
            raise serializers.ValidationError(
                "Refresh token باید یک رشته باشد."
            )
        if value.count('.') != 2:
            raise serializers.ValidationError(
                "فرمت refresh token نامعتبر است."
            )
        return value
