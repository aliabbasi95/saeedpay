# apps/blogs/api/public/v1/serializers/article.py

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiTypes, extend_schema_field
from rest_framework import serializers

from apps.blogs.api.public.v1.serializers.tag import TagListSerializer
from apps.blogs.models import Article, ArticleSection

User = get_user_model()


class AuthorSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "full_name"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_full_name(self, obj):
        """Safely resolve the author's display name."""
        profile = None
        try:
            profile = obj.profile
        except Exception:
            profile = None

        if profile and getattr(profile, "full_name", None):
            return profile.full_name
        return getattr(obj, "get_full_name", lambda: "")() or obj.username


class ArticleSectionSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(read_only=True)

    class Meta:
        model = ArticleSection
        fields = ["id", "section_type", "content", "image", "image_alt", "order"]

    def validate(self, data):
        """Validate section content based on section type."""
        section_type = data.get("section_type")
        content = data.get("content")
        image = data.get("image")

        if section_type == "image":
            if not image:
                raise serializers.ValidationError(
                    {"image": _("تصویر برای بخش تصویری الزامی است")}
                )
            if content:
                raise serializers.ValidationError(
                    {"content": _("بخش تصویری نباید محتوای متنی داشته باشد")}
                )
        else:
            if not content:
                raise serializers.ValidationError(
                    {"content": _("محتوا برای این نوع بخش الزامی است")}
                )
            if image:
                raise serializers.ValidationError(
                    {"image": _("بخش متنی نباید تصویر داشته باشد")}
                )
        return data


class ArticleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing articles."""

    author = AuthorSerializer(read_only=True)

    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "slug",
            "author",
            "excerpt",
            "featured_image",
            "published_at",
        ]


class ArticleDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for a single article."""

    author = AuthorSerializer(read_only=True)
    tags = TagListSerializer(many=True, read_only=True)
    sections = serializers.SerializerMethodField()
    rendered_content = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    jalali_creation_date_time = serializers.CharField(read_only=True)
    jalali_update_date_time = serializers.CharField(read_only=True)

    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "slug",
            "author",
            "rendered_content",
            "excerpt",
            "featured_image",
            "status",
            "tags",
            "sections",
            "is_featured",
            "published_at",
            "view_count",
            "comment_count",
            "jalali_creation_date_time",
            "jalali_update_date_time",
            "comments",
        ]

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_sections(self, obj):
        """Return article sections ordered by their display order."""
        sections = obj.sections.all().order_by("order")
        return ArticleSectionSerializer(sections, many=True).data

    @extend_schema_field(OpenApiTypes.STR)
    def get_rendered_content(self, obj):
        """Return rendered HTML content for the article."""
        return obj.render_content()

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_comments(self, obj):
        """Return approved root-level comments."""
        from apps.blogs.api.public.v1.serializers.comment import CommentListSerializer

        approved_roots = obj.comments.filter(
            is_approved=True,
            reply_to__isnull=True,
        ).order_by("created_at")
        return CommentListSerializer(
            approved_roots,
            many=True,
            context=self.context,
        ).data

    @extend_schema_field(OpenApiTypes.INT)
    def get_comment_count(self, obj):
        """Use annotated comment count when available."""
        annotated = getattr(obj, "approved_comment_count", None)
        if annotated is not None:
            return annotated
        return obj.comment_count
