# blogs/api/public/v1/serializers/article.py

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from blogs.models import Article, ArticleSection
from .tag import TagListSerializer

User = get_user_model()


class AuthorSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "full_name"]

    def get_full_name(self, obj):
        """
        Safe access to optional profile.full_name.
        Falls back to Django's get_full_name() then username.
        """
        profile = None
        try:
            profile = obj.profile
        except Exception:
            profile = None
        if profile and getattr(profile, "full_name", None):
            return profile.full_name
        return (getattr(obj, "get_full_name", lambda: "")() or obj.username)


class ArticleSectionSerializer(serializers.ModelSerializer):
    # Read-only image URL for public API
    image = serializers.ImageField(read_only=True)

    class Meta:
        model = ArticleSection
        fields = ["id", "section_type", "content", "image", "image_alt",
                  "order"]

    def validate(self, data):
        """
        Validate mutually exclusive content/image based on section_type.
        """
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
        fields = ["id", "title", "slug", "author", "excerpt", "featured_image",
                  "published_at"]


class ArticleDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for a single article.
    Uses prefetch'ed relations supplied by the view for efficiency.
    """
    author = AuthorSerializer(read_only=True)
    tags = TagListSerializer(many=True, read_only=True)
    sections = serializers.SerializerMethodField()
    rendered_content = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()

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

    def get_sections(self, obj):
        """
        Return sections ordered by 'order'.
        Assumes sections are prefetch'ed.
        """
        sections = obj.sections.all().order_by("order")
        return ArticleSectionSerializer(sections, many=True).data

    def get_rendered_content(self, obj):
        """Return article HTML built from sections."""
        return obj.render_content()

    def get_comments(self, obj):
        """
        Return approved root-level comments with limited nested replies.
        Prefetch should be configured in the view.
        """
        from blogs.api.public.v1.serializers.comment import \
            CommentListSerializer

        approved_roots = obj.comments.filter(
            is_approved=True, reply_to__isnull=True
        ).order_by("created_at")
        return CommentListSerializer(
            approved_roots, many=True, context=self.context
        ).data

    def get_comment_count(self, obj):
        """
        Use annotated count if available; otherwise fall back to property.
        """
        annotated = getattr(obj, "approved_comment_count", None)
        if annotated is not None:
            return annotated
        return obj.comment_count
