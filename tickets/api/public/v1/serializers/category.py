# tickets/api/public/v1/serializers/category.py

from rest_framework import serializers

from tickets.models import TicketCategory


class TicketCategoryListSerializer(serializers.ModelSerializer):
    """لیست دسته‌بندی‌ها - فقط id، name و description"""

    class Meta:
        model = TicketCategory
        fields = ["id", "name", "description"]


class TicketCategoryDetailSerializer(serializers.ModelSerializer):
    """جزئیات کامل دسته‌بندی"""

    class Meta:
        model = TicketCategory
        fields = ["id", "name", "description", "icon", "color"]
