# blogs/api/public/v1/views/article.py

from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from blogs.api.public.v1.schema import article_viewset_schema
from blogs.api.public.v1.serializers import (
    ArticleListSerializer,
    ArticleDetailSerializer,
)
from blogs.filters import ArticleFilter
from blogs.models import Article, Comment


@article_viewset_schema
class ArticleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for Article.
    - List: published & time passed for non-authors; include author's own drafts if authenticated.
    - Retrieve: same visibility; increments view_count atomically.
    """
    serializer_class = ArticleListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ArticleFilter
    search_fields = ["title", "sections__content", "excerpt"]
    ordering_fields = ["created_at", "published_at", "view_count", "title"]
    ordering = ["-created_at"]
    lookup_field = "slug"

    def get_object(self):
        """
        Override to support both ID and slug lookup.
        """
        lookup_value = self.kwargs.get(self.lookup_url_kwarg or self.lookup_field)
        
        # Try to determine if it's an ID (numeric) or slug (string)
        if lookup_value.isdigit():
            # It's an ID, use pk lookup
            queryset = self.get_queryset()
            obj = queryset.filter(pk=lookup_value).first()
            if obj is None:
                from rest_framework.exceptions import NotFound
                raise NotFound("Article not found")
            return obj
        else:
            # It's a slug, use slug lookup
            return super().get_object()

    def get_queryset(self):
        now = timezone.now()

        # Base queryset
        qs = Article.objects.select_related("author__profile")

        # Visibility rules
        if self.action in ["list", "retrieve"]:
            if self.request.user.is_authenticated:
                qs = qs.filter(
                    Q(author=self.request.user) | Q(
                        status="published", published_at__lte=now
                    )
                )
            else:
                qs = qs.filter(status="published", published_at__lte=now)

        # Prefetch tune per action
        if self.action == "list":
            qs = qs.prefetch_related("tags").distinct()
        else:  # retrieve
            qs = qs.prefetch_related(
                "tags",
                Prefetch(
                    "sections",
                    queryset=Article.sections.rel.related_model.objects.order_by(
                        "order"
                    )
                ),
                Prefetch(
                    "comments",
                    queryset=Comment.objects.select_related("author").filter(
                        is_approved=True
                    ).order_by("created_at"),
                ),
            ).annotate(
                approved_comment_count=Count(
                    "comments", filter=Q(
                        comments__is_approved=True
                    ), distinct=True
                )
            ).distinct()

        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return ArticleListSerializer
        return ArticleDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        """
        Override retrieve to increment view count atomically.
        """
        instance = self.get_object()
        instance.increment_view_count()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
