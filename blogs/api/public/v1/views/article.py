# blogs/api/public/v1/views/article.py

from django.db.models import Count, Prefetch, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from blogs.api.public.v1.schema import article_viewset_schema
from blogs.api.public.v1.serializers import (
    ArticleDetailSerializer,
    ArticleListSerializer,
)
from blogs.filters import ArticleFilter
from blogs.models import Article, ArticleSection, Comment


@article_viewset_schema
class ArticleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for articles.

    List:
        Published articles for anonymous users, plus authenticated authors' own drafts.
    Retrieve:
        Same visibility rules, with atomic view-count increment.
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
        """Support lookup by numeric ID or slug."""
        lookup_value = self.kwargs.get(self.lookup_url_kwarg or self.lookup_field)

        if lookup_value.isdigit():
            queryset = self.get_queryset()
            obj = queryset.filter(pk=lookup_value).first()
            if obj is None:
                from rest_framework.exceptions import NotFound

                raise NotFound("Article not found")
            return obj

        return super().get_object()

    def get_queryset(self):
        now = timezone.localtime(timezone.now())
        queryset = Article.objects.select_related("author", "author__profile")

        if self.action in ["list", "retrieve"]:
            if self.request.user.is_authenticated:
                queryset = queryset.filter(
                    Q(author=self.request.user)
                    | Q(status="published", published_at__lte=now)
                )
            else:
                queryset = queryset.filter(status="published", published_at__lte=now)

        if self.action == "list":
            queryset = (
                queryset.only(
                    "id",
                    "title",
                    "slug",
                    "excerpt",
                    "featured_image",
                    "published_at",
                    "author__id",
                    "author__username",
                    "author__profile__first_name",
                    "author__profile__last_name",
                )
                .prefetch_related("tags")
                .distinct()
            )
        else:
            queryset = (
                queryset.prefetch_related(
                    "tags",
                    Prefetch(
                        "sections",
                        queryset=ArticleSection.objects.only(
                            "id",
                            "section_type",
                            "content",
                            "image",
                            "image_alt",
                            "order",
                            "article_id",
                        ).order_by("order"),
                    ),
                    Prefetch(
                        "comments",
                        queryset=Comment.objects.select_related(
                            "author",
                            "author__profile",
                        )
                        .only(
                            "id",
                            "content",
                            "rating",
                            "reply_to_id",
                            "is_approved",
                            "like_count",
                            "dislike_count",
                            "created_at",
                            "article_id",
                            "store_id",
                            "author__id",
                            "author__username",
                            "author__first_name",
                            "author__last_name",
                        )
                        .filter(is_approved=True)
                        .order_by("created_at"),
                    ),
                )
                .annotate(
                    approved_comment_count=Count(
                        "comments",
                        filter=Q(comments__is_approved=True),
                        distinct=True,
                    )
                )
                .distinct()
            )

        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return ArticleListSerializer
        return ArticleDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        """Increment view count atomically and return article details."""
        instance = self.get_object()
        instance.increment_view_count()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
