# blogs/filters.py

from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters

from blogs.models import Article
from blogs.utils.choices import ArticleStatus


class NumberInFilter(filters.BaseInFilter, filters.NumberFilter):
    """
    Filter for passing multiple numeric values, e.g. ?tags=1&tags=2
    Generates an `__in` lookup behind the scenes.
    """
    pass


class ArticleFilter(filters.FilterSet):
    """
    Filters for Article model.
    - tags: filter by multiple tag IDs (?tags=1&tags=2)
    - is_featured: featured flag
    - status: Article status (draft/published/archived)
    - author: author id
    - published_after/before: range on `published_at`
    """

    tags = NumberInFilter(
        field_name="tags",
        lookup_expr="in",
        help_text=_("فیلتر بر اساس برچسب‌ها (می‌توانید چند مقدار ارسال کنید)")
    )

    is_featured = filters.BooleanFilter(
        field_name="is_featured",
        help_text=_("فیلتر مقالات ویژه")
    )

    status = filters.ChoiceFilter(
        field_name="status",
        choices=ArticleStatus.choices,
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
        fields = [
            "tags",
            "is_featured",
            "status",
            "author",
            "published_after",
            "published_before",
        ]

    def filter_queryset(self, queryset):
        """
        Ensure distinct results when using M2M filters like `tags__in`.
        """
        qs = super().filter_queryset(queryset)
        return qs.distinct()
