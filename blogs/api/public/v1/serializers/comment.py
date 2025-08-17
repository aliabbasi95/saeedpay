# blogs/api/public/v1/serializers/comment.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from blogs.models import Comment

User = get_user_model()


class CommentAuthorSerializer(serializers.ModelSerializer):
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']

    @extend_schema_field(serializers.CharField)
    def get_first_name(self, obj) -> str:
        if hasattr(obj, 'profile') and obj.profile.first_name:
            return obj.profile.first_name
        return ''

    @extend_schema_field(serializers.CharField)
    def get_last_name(self, obj) -> str:
        if hasattr(obj, 'profile') and obj.profile.last_name:
            return obj.profile.last_name
        return ''


class CommentSerializer(serializers.ModelSerializer):
    """Basic comment serializer"""
    author = CommentAuthorSerializer(read_only=True)
    reply_count = serializers.SerializerMethodField()
    jalali_creation_date_time = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id',
            'author',
            'reply_to',
            'content',
            'rating',
            'is_approved',
            'reply_count',
            'like_count',
            'dislike_count',
            'jalali_creation_date_time',
        ]
        read_only_fields = ['is_approved', 'like_count', 'dislike_count']
    
    @extend_schema_field(serializers.IntegerField)
    def get_reply_count(self, obj) -> int:
        return obj.reply_count
    
    @extend_schema_field(serializers.CharField)
    def get_jalali_creation_date_time(self, obj) -> str:
        return obj.jalali_creation_date_time


class CommentListSerializer(serializers.ModelSerializer):
    """Serializer for comment lists with nested replies"""
    author = CommentAuthorSerializer(read_only=True)
    replies = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()
    jalali_creation_date_time = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id',
            'author',
            'content',
            'rating',
            'reply_count',
            'replies',
            'like_count',
            'dislike_count',
            'jalali_creation_date_time',
        ]
    
    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_replies(self, obj):
        """Get approved direct replies"""
        if obj.reply_to is None:  # Only get replies for root comments
            replies = obj.get_replies()[:5]  # Limit to 5 replies
            return CommentSerializer(replies, many=True, context=self.context).data
        return []
    
    @extend_schema_field(serializers.IntegerField)
    def get_reply_count(self, obj) -> int:
        return obj.reply_count
    
    @extend_schema_field(serializers.CharField)
    def get_jalali_creation_date_time(self, obj) -> str:
        return obj.jalali_creation_date_time


class CommentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating comments"""
    
    class Meta:
        model = Comment
        fields = [
            'article',
            'reply_to',
            'content',
            'rating',
        ]
    
    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("امتیاز باید بین 1 تا 5 باشد.")
        return value
    
    def validate(self, attrs):
        # Validate reply_to comment belongs to same article
        reply_to = attrs.get('reply_to')
        article = attrs.get('article')
        
        if reply_to and article and reply_to.article != article:
            raise serializers.ValidationError(
                "نظر پاسخ باید متعلق به همان مقاله باشد."
            )
        
        # If replying to a comment, article should be the same as reply_to's article
        if reply_to and not article:
            attrs['article'] = reply_to.article
        
        return attrs
    
    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user:
            validated_data['author'] = request.user
        return super().create(validated_data)


class CommentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating comments"""
    
    class Meta:
        model = Comment
        fields = ['content', 'rating']
    
    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("امتیاز باید بین 1 تا 5 باشد.")
        return value
    
    def update(self, instance, validated_data):
        # Only allow author to update their own comments
        request = self.context.get('request')
        if request and request.user != instance.author:
            raise serializers.ValidationError("شما فقط می‌توانید نظرات خود را ویرایش کنید.")
        
        return super().update(instance, validated_data)
