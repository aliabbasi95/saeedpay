# store/api/public/v1/serializers/store.py
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from store.models import Store


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
        """Calculate average rating from store comments, default to 75% if no comments"""
        from django.db.models import Avg

        # Get approved comments for this store
        approved_comments = obj.comments.filter(
            is_approved=True, article__isnull=True
        )

        if approved_comments.exists():
            # Calculate average rating (1-5 scale) and convert to percentage
            avg_rating = approved_comments.aggregate(avg=Avg('rating'))['avg']
            return round((avg_rating / 5.0) * 100, 1)  # Convert to percentage
        else:
            # Default to 75% for stores with no comments
            return 75.0

    def update(self, instance, validated_data):
        # Don't modify verification here - let the view handle it
        # Cardboard will automatically calculate status based on verification fields
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
    """Public serializer for stores - only shows approved/active stores with limited fields"""

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
        """Calculate average rating from store comments, default to 75% if no comments"""
        from django.db.models import Avg

        # Get approved comments for this store
        approved_comments = obj.comments.filter(
            is_approved=True, article__isnull=True
        )

        if approved_comments.exists():
            # Calculate average rating (1-5 scale) and convert to percentage
            avg_rating = approved_comments.aggregate(avg=Avg('rating'))['avg']
            return round((avg_rating / 5.0) * 100, 1)  # Convert to percentage
        else:
            # Default to 75% for stores with no comments
            return 75.0
