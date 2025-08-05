from rest_framework import serializers

from store.models import Store


class StoreSerializer(serializers.ModelSerializer):
    verification_status = serializers.CharField(
        source="get_status", read_only=True
    )

    class Meta:
        model = Store
        fields = [
            "id",
            "name",
            "code",
            "address",
            "is_active",
            "verification_status",
            "verification_time",
        ]


class StoreCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = [
            "name",
            "code",
            "address",
        ]
