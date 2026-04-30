# apps/store/api/public/v1/serializers/store.py

from django.db.models import Avg
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.store.models import Store


class StoreSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status", read_only=True)
    rating = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = [
            "id",
            "name",
            "code",
            "address",
            "longitude",
            "latitude",
            "website_url",
            "status_display",
            "logo",
            "rating",
            "is_active",
            "verification_time",
        ]
        read_only_fields = [
            "code",
            "is_active",
            "status",
            "status_display",
            "rating",
            "verification_time",
        ]

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_rating(self, obj):
        approved_comments = obj.comments.filter(
            is_approved=True,
            article__isnull=True,
        )

        if approved_comments.exists():
            avg_rating = approved_comments.aggregate(avg=Avg("rating"))["avg"]
            return round((avg_rating / 5.0) * 100, 1)

        return 75.0

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)


class StoreCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = [
            "name",
            "address",
            "longitude",
            "latitude",
            "website_url",
            "logo",
        ]


class PublicStoreSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status", read_only=True)
    rating = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = [
            "id",
            "name",
            "address",
            "longitude",
            "latitude",
            "website_url",
            "status",
            "status_display",
            "logo",
            "rating",
        ]
        read_only_fields = [
            "id",
            "name",
            "address",
            "longitude",
            "latitude",
            "website_url",
            "status",
            "status_display",
            "logo",
            "rating",
        ]

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_rating(self, obj):
        approved_comments = obj.comments.filter(
            is_approved=True,
            article__isnull=True,
        )

        if approved_comments.exists():
            avg_rating = approved_comments.aggregate(avg=Avg("rating"))["avg"]
            return round((avg_rating / 5.0) * 100, 1)

        return 75.0
