# blogs/api/public/v1/serializers/article.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from blogs.models import Article, ArticleSection
from .tag import TagListSerializer

User = get_user_model()


class AuthorSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name']

    def get_full_name(self, obj):
        if hasattr(obj, 'profile') and obj.profile:
            return obj.profile.full_name
        return obj.username


class ArticleSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleSection
        fields = [
            'id',
            'section_type',
            'content',
            'image',
            'image_alt',
            'order',
        ]
    
    def validate(self, data):
        """Validate mutually exclusive content/image based on section type"""
        section_type = data.get('section_type')
        content = data.get('content')
        image = data.get('image')
        
        if section_type == 'image':
            if not image:
                raise serializers.ValidationError({
                    'image': _('تصویر برای بخش تصویری الزامی است')
                })
            if content:
                raise serializers.ValidationError({
                    'content': _('بخش تصویری نباید محتوای متنی داشته باشد')
                })
        else:
            if not content:
                raise serializers.ValidationError({
                    'content': _('محتوا برای این نوع بخش الزامی است')
                })
            if image:
                raise serializers.ValidationError({
                    'image': _('بخش متنی نباید تصویر داشته باشد')
                })
        
        return data


class ArticleListSerializer(serializers.ModelSerializer):
    """Simplified serializer for article lists"""
    author = AuthorSerializer(read_only=True)
    
    class Meta:
        model = Article
        fields = [
            'id',
            'title',
            'slug',
            'author',
            'excerpt',
            'featured_image',
            'published_at',
        ]


class ArticleDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for individual article views"""
    author = AuthorSerializer(read_only=True)
    tags = TagListSerializer(many=True, read_only=True)
    sections = serializers.SerializerMethodField()
    comment_count = serializers.ReadOnlyField()
    rendered_content = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = [
            'id',
            'title',
            'slug',
            'author',
            'rendered_content',
            'excerpt',
            'featured_image',
            'status',
            'tags',
            'sections',
            'is_featured',
            'published_at',
            'view_count',
            'comment_count',
            'jalali_creation_date_time',
            'jalali_update_date_time',
            'comments',
        ]

    def get_sections(self, obj):
        """Get sections ordered by order field"""
        sections = obj.sections.all().order_by('order')
        return ArticleSectionSerializer(sections, many=True).data

    def get_rendered_content(self, obj):
        """Get content rendered as HTML from sections"""
        return obj.render_content()

    def get_comments(self, obj):
        from blogs.api.public.v1.serializers.comment import CommentListSerializer
        approved_comments = obj.comments.filter(is_approved=True, reply_to=None).order_by('created_at')
        return CommentListSerializer(approved_comments, many=True, context=self.context).data


    
