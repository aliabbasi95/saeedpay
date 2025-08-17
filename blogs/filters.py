# blogs/filters.py
from django_filters import rest_framework as filters
from django.utils.translation import gettext_lazy as _

from blogs.models import Article, Tag


class ArticleFilter(filters.FilterSet):
    """Filter for Article model with tag and featured filtering"""
    
    tags = filters.BaseInFilter(
        field_name="tags",
        lookup_expr="in",
        help_text=_("فیلتر بر اساس برچسب‌ها")
    )
    
    is_featured = filters.BooleanFilter(
        field_name="is_featured",
        help_text=_("فیلتر مقالات ویژه")
    )
    
    status = filters.ChoiceFilter(
        field_name="status",
        choices=Article.STATUS_CHOICES,
        help_text=_("فیلتر بر اساس وضعیت")
    )
    
    author = filters.NumberFilter(
        field_name="author_id",
        help_text=_("فیلتر بر اساس نویسنده")
    )
    
    published_after = filters.DateTimeFilter(
        field_name="published_at",
        lookup_expr="gte",
        help_text=_("مقالات منتشر شده بعد از تاریخ مشخص")
    )
    
    published_before = filters.DateTimeFilter(
        field_name="published_at",
        lookup_expr="lte",
        help_text=_("مقالات منتشر شده قبل از تاریخ مشخص")
    )

    class Meta:
        model = Article
        fields = ["tags", "is_featured", "status", "author", "published_after", "published_before"]
