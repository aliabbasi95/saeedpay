# blogs/api/public/v1/views/tag.py

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import AllowAny

from blogs.api.public.v1.schema import tag_viewset_schema
from blogs.api.public.v1.serializers import TagSerializer, TagListSerializer
from blogs.models import Tag
from django.db.models import Count, Q


@tag_viewset_schema
class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only Tag API."""
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    filterset_fields = ["is_active"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        return (
            Tag.objects
            .filter(is_active=True)
            .annotate(
                article_count=Count(
                    "articles",
                    filter=Q(articles__status="published"),
                    distinct=True,
                )
            )
            .only("id", "name", "slug", "description", "color", "is_active")
        )

    def get_serializer_class(self):
        if self.action == "list":
            return TagListSerializer
        return TagSerializer
