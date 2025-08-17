# blogs/api/public/v1/serializers/tag.py
from rest_framework import serializers
from blogs.models import Tag


class TagSerializer(serializers.ModelSerializer):
    article_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Tag
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'color',
            'is_active',
            'article_count',
        ]


class TagListSerializer(serializers.ModelSerializer):
    """Simplified tag serializer for lists"""
    
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug', 'color']
