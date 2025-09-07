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

from blogs.api.public.v1.permissions import IsOwnerOrStaff
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
    - List supports filtering by article and reply_to.
    - Updates/deletes restricted to owner or staff.
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    recaptcha_actions = {"create"}
    recaptcha_action_name = "comment"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = {'article': ['exact'], 'store': ['exact']}
    ordering_fields = ['created_at', 'like_count']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = (
            Comment.objects.select_related("author", "article", "reply_to")
            .prefetch_related("replies")
        )

        # Visible to everyone: approved comments
        # Authenticated users also see their own (any status)
        if self.request.user.is_authenticated:
            qs = qs.filter(Q(author=self.request.user) | Q(is_approved=True))
        else:
            # Anonymous users only see approved comments
            qs = qs.filter(is_approved=True)
        
        # For list action, only return root comments (replies are included via serializer)
        if self.action == 'list':
            qs = qs.filter(reply_to__isnull=True)
        
        return qs
    
    def get_serializer_class(self):
        if self.action == "list":
            return CommentListSerializer
        elif self.action == "create":
            return CommentCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return CommentUpdateSerializer
        return CommentSerializer

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(author=self.request.user)
        else:
            serializer.save(author=None)

    def get_permissions(self):
        """
        Owner-or-staff required for updates/deletes.
        AllowAny for create/like/dislike (protected by reCAPTCHA for create).
        """
        if self.action in ["create", "like", "dislike"]:
            permission_classes = [AllowAny]
        elif self.action in ["update", "partial_update", "destroy"]:
            permission_classes = [IsAuthenticated, IsOwnerOrStaff]
        else:
            permission_classes = [IsAuthenticatedOrReadOnly]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=["get"])
    def my_comments(self, request):
        """Return current user's comments (requires authentication)."""
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        queryset = Comment.objects.filter(author=request.user).select_related(
            "article", "reply_to"
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CommentSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = CommentSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def orphaned_comments(self, request):
        """
        Get comments that are not linked to any article or store (both fields are null).
        Supports ordering by created_at, like_count, and dislike_count.
        """
        queryset = self.get_queryset().filter(
            article__isnull=True, store__isnull=True
        )
        
        # Apply ordering
        ordering = request.query_params.get('ordering', '-created_at')
        if ordering in ['created_at', '-created_at', 'like_count', '-like_count', 'dislike_count', '-dislike_count']:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by('-created_at')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CommentListSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = CommentListSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def like(self, request, pk=None):
        """Atomically increment like_count for a comment."""
        comment = self.get_object()
        Comment.objects.filter(pk=comment.pk).update(
            like_count=F("like_count") + 1
        )
        comment.refresh_from_db(fields=["like_count", "dislike_count"])
        return Response(
            {
                "id": comment.pk, "like_count": comment.like_count,
                "dislike_count": comment.dislike_count
            }
        )

    @action(detail=True, methods=["post"])
    def dislike(self, request, pk=None):
        """Atomically increment dislike_count for a comment."""
        comment = self.get_object()
        Comment.objects.filter(pk=comment.pk).update(
            dislike_count=F("dislike_count") + 1
        )
        comment.refresh_from_db(fields=["like_count", "dislike_count"])
        return Response(
            {
                "id": comment.pk, "like_count": comment.like_count,
                "dislike_count": comment.dislike_count
            }
        )
