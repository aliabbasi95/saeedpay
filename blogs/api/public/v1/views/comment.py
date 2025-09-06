# blogs/api/public/v1/views/comment.py
from django.db.models import Q, F
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import (
    IsAuthenticatedOrReadOnly,
    IsAuthenticated, AllowAny,
)
from rest_framework.response import Response

from blogs.api.public.v1.schema import comment_viewset_schema
from blogs.api.public.v1.serializers import (
    CommentListSerializer,
    CommentSerializer,
    CommentCreateSerializer,
    CommentUpdateSerializer,
)
from blogs.models import Comment
from utils.recaptcha import ReCaptchaMixin


@comment_viewset_schema
class CommentViewSet(ReCaptchaMixin, viewsets.ModelViewSet):
    """
    ViewSet for comments with moderation support.

    Supports filtering by article pk (nullable) and reply_to pk using django-filter.
    - To get comments for a specific article: ?article=<article_id>
    - To get comments not related to any article: ?article__isnull=true
    - To get replies to a specific comment: ?reply_to=<comment_id>
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    recaptcha_actions = {'create'}
    recaptcha_action_name = 'comment'
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = {'article': ['exact', 'isnull'], 'reply_to': ['exact']}
    ordering_fields = ['created_at', 'like_count']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Comment.objects.select_related(
            'author', 'article', 'reply_to'
            ).prefetch_related('replies')

        # Only show approved comments to non-authors
        if self.request.user.is_authenticated:
            # Show user's own comments (any status) + approved comments from others
            queryset = queryset.filter(
                Q(author=self.request.user) | Q(is_approved=True)
            )
        else:
            # Anonymous users only see approved comments
            queryset = queryset.filter(is_approved=True)

        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return CommentListSerializer
        elif self.action == 'create':
            return CommentCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return CommentUpdateSerializer
        return CommentSerializer

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(author=self.request.user)
        else:
            serializer.save(author=None)

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['create', 'like', 'dislike']:
            permission_classes = [AllowAny]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticatedOrReadOnly]

        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'])
    def my_comments(self, request):
        """Get current user's comments"""
        if not request.user.is_authenticated:
            return Response(
                {'detail': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
                )

        queryset = Comment.objects.filter(author=request.user).select_related(
            'article', 'reply_to'
            )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CommentSerializer(
                page, many=True, context={'request': request}
                )
            return self.get_paginated_response(serializer.data)

        serializer = CommentSerializer(
            queryset, many=True, context={'request': request}
            )
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def article_comments(self, request):
        """Get comments for a specific article"""
        article_id = request.query_params.get('article_id')
        if not article_id:
            return Response(
                {'detail': 'article_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
                )

        # Only get root comments (no reply_to) - replies are included in serializer
        queryset = self.get_queryset().filter(
            article_id=article_id, reply_to__isnull=True
            )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CommentListSerializer(
                page, many=True, context={'request': request}
                )
            return self.get_paginated_response(serializer.data)

        serializer = CommentListSerializer(
            queryset, many=True, context={'request': request}
            )
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        """Increment like_count for a comment"""
        comment = self.get_object()
        Comment.objects.filter(pk=comment.pk).update(
            like_count=F('like_count') + 1
            )
        comment.refresh_from_db(fields=['like_count', 'dislike_count'])
        return Response(
            {
                'id': comment.pk,
                'like_count': comment.like_count,
                'dislike_count': comment.dislike_count,
            }
        )

    @action(detail=True, methods=['post'])
    def dislike(self, request, pk=None):
        """Increment dislike_count for a comment"""
        comment = self.get_object()
        Comment.objects.filter(pk=comment.pk).update(
            dislike_count=F('dislike_count') + 1
            )
        comment.refresh_from_db(fields=['like_count', 'dislike_count'])
        return Response(
            {
                'id': comment.pk,
                'like_count': comment.like_count,
                'dislike_count': comment.dislike_count,
            }
        )
