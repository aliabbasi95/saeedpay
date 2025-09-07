# blogs/api/public/v1/serializers/comment.py

from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from blogs.models import Comment
from store.models import Store
from utils.recaptcha import ReCaptchaField
from blogs.models import Article


User = get_user_model()


class CommentAuthorSerializer(serializers.ModelSerializer):
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]

    @extend_schema_field(serializers.CharField)
    def get_first_name(self, obj) -> str:
        # Safe access to optional profile.first_name
        try:
            prof = obj.profile
            if getattr(prof, "first_name", None):
                return prof.first_name
        except Exception:
            pass
        return ""

    @extend_schema_field(serializers.CharField)
    def get_last_name(self, obj) -> str:
        # Safe access to optional profile.last_name
        try:
            prof = obj.profile
            if getattr(prof, "last_name", None):
                return prof.last_name
        except Exception:
            pass
        return ""


class CommentSerializer(serializers.ModelSerializer):
    """Basic comment serializer."""

    author = CommentAuthorSerializer(read_only=True)
    reply_count = serializers.SerializerMethodField()
    jalali_creation_date_time = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "author",
            "reply_to",
            "content",
            "rating",
            "is_approved",
            "reply_count",
            "like_count",
            "dislike_count",
            "jalali_creation_date_time",
        ]
        read_only_fields = ["is_approved", "like_count", "dislike_count"]

    @extend_schema_field(serializers.IntegerField)
    def get_reply_count(self, obj) -> int:
        return obj.reply_count

    @extend_schema_field(serializers.CharField)
    def get_jalali_creation_date_time(self, obj) -> str:
        return obj.jalali_creation_date_time


class CommentListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing root comments with a limited set of direct replies.
    """
    author = CommentAuthorSerializer(read_only=True)
    replies = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()
    jalali_creation_date_time = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "author",
            "content",
            "rating",
            "reply_count",
            "replies",
            "like_count",
            "dislike_count",
            "jalali_creation_date_time",
        ]

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_replies(self, obj):
        """
        Return up to 5 approved direct replies.
        NOTE: Deep nesting should be handled in the client if needed.
        """
        if obj.reply_to is None:
            replies = obj.get_replies()[:5]
            return CommentSerializer(
                replies, many=True, context=self.context
            ).data
        return []

    @extend_schema_field(serializers.IntegerField)
    def get_reply_count(self, obj) -> int:
        return obj.reply_count

    @extend_schema_field(serializers.CharField)
    def get_jalali_creation_date_time(self, obj) -> str:
        return obj.jalali_creation_date_time


class CommentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating comments."""
    recaptcha_token = ReCaptchaField(required=True)

    class Meta:
        model = Comment
        fields = [
            "article",
            "store",
            "reply_to",
            "content",
            "rating",
            "recaptcha_token",
        ]

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("امتیاز باید بین 1 تا 5 باشد.")
        return value

    def validate_article(self, value):
        """Validate article exists, set to None if it doesn't"""
        if value is not None:
            try:
                Article.objects.get(pk=value.pk)
                return value
            except Article.DoesNotExist:
                return None
        return value

    def validate_store(self, value):
        """Validate store exists, set to None if it doesn't"""
        if value is not None:
            try:
                Store.objects.get(pk=value.pk)
                return value
            except Store.DoesNotExist:
                return None
        return value

    def validate(self, attrs):
        reply_to = attrs.get("reply_to")
        article = attrs.get("article")
        store = attrs.get("store")

        # Prevent both article and store being provided
        if article is not None and store is not None:
            raise serializers.ValidationError(
                "نظر نمی‌تواند همزمان به مقاله و فروشگاه مرتبط باشد."
            )

        # Handle reply validation
        if reply_to:
            # Validate reply_to comment belongs to same article/store
            if article and reply_to.article != article:
                raise serializers.ValidationError(
                    "نظر پاسخ باید متعلق به همان مقاله باشد."
                )
            if store and reply_to.store != store:
                raise serializers.ValidationError(
                    "نظر پاسخ باید متعلق به همان فروشگاه باشد."
                )

            # If replying to a comment, inherit the parent's article/store
            if not article and not store:
                attrs["article"] = reply_to.article
                attrs["store"] = reply_to.store
            elif article and not store:
                # Ensure we're replying to an article comment
                if reply_to.store is not None:
                    raise serializers.ValidationError(
                        "نمی‌توان به نظر فروشگاه، پاسخ مقاله داد."
                    )
            elif store and not article:
                # Ensure we're replying to a store comment
                if reply_to.article is not None:
                    raise serializers.ValidationError(
                        "نمی‌توان به نظر مقاله، پاسخ فروشگاه داد."
                    )

        return attrs


class CommentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating comments by their owner."""

    class Meta:
        model = Comment
        fields = ["content", "rating"]

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("امتیاز باید بین 1 تا 5 باشد.")
        return value

    def update(self, instance, validated_data):
        # Enforce author-only updates
        request = self.context.get("request")
        if request and request.user != instance.author:
            raise serializers.ValidationError(
                "شما فقط می‌توانید نظرات خود را ویرایش کنید."
            )

        return super().update(instance, validated_data)
