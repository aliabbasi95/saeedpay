# blogs/api/public/v1/views/article.py
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from blogs.filters import ArticleFilter
from blogs.api.public.v1.schema import article_viewset_schema
from django.db.models import Q

from lib.cas_auth.erp.pagination import CustomPagination
from blogs.models import Article
from blogs.api.public.v1.serializers import (
    ArticleListSerializer,
    ArticleDetailSerializer,
)


@article_viewset_schema
class ArticleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for Article model exposing only list and retrieve.
    """
    serializer_class = ArticleListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ArticleFilter
    search_fields = ['title', 'content', 'excerpt']
    ordering_fields = ['created_at', 'published_at', 'view_count', 'title']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = Article.objects.select_related('author__profile').prefetch_related('tags', 'sections', 'comments')
        
        # For list view, only show published articles to non-authors
        if self.action == 'list':
            if self.request.user.is_authenticated:
                # Show user's own articles (any status) + published articles from others
                queryset = queryset.filter(
                    Q(author=self.request.user) | Q(status='published')
                )
            else:
                # Anonymous users only see published articles
                queryset = queryset.filter(status='published')
        
        # For detail view, check permissions
        elif self.action == 'retrieve':
            if self.request.user.is_authenticated:
                # Show user's own articles + published articles
                queryset = queryset.filter(
                    Q(author=self.request.user) | Q(status='published')
                )
            else:
                # Anonymous users only see published articles
                queryset = queryset.filter(status='published')
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ArticleListSerializer
        return ArticleDetailSerializer
    
    def retrieve(self, request, *args, **kwargs):
        """Override retrieve to increment view count"""
        instance = self.get_object()
        
        # Increment view count
        instance.increment_view_count()
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

