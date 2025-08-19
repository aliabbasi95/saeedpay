# chatbot/api/public/v1/views/session.py

from django.db.models import Max, F, Prefetch
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from chatbot.api.public.v1.serializers import (
    ChatSessionSerializer,
    ChatSessionDetailSerializer,
)
from chatbot.models import ChatSession, ChatMessage
from lib.cas_auth.views import PublicGetAPIView


@extend_schema(
    tags=["Chatbot"],
    summary="List user chat sessions",
    description="""
    List chat sessions belonging to the current user (if authenticated) or \
the current anonymous session (if not authenticated). Sessions are ordered by \
creation time descending.
    """,
    responses=ChatSessionSerializer(many=True),
)
class UserChatSessionsView(PublicGetAPIView):
    """
    List chat sessions belonging to the current user (or anonymous session).
    """

    serializer_class = ChatSessionSerializer
    permission_classes = [AllowAny]

    def get(self, request):
        if request.user.is_authenticated:
            base_qs = ChatSession.objects.filter(user=request.user)
        else:
            session_key = request.session.session_key
            if not session_key:
                base_qs = ChatSession.objects.none()
            else:
                base_qs = ChatSession.objects.filter(
                    user=None, session_key=session_key
                )

        qs = (
            base_qs
            .annotate(last_msg_at=Max("messages__created_at"))
            .annotate(last_sort_at=Coalesce(F("last_msg_at"), F("created_at")))
            .order_by("-last_sort_at")
        )

        serializer = self.get_serializer(qs, many=True)
        self.response_data = serializer.data
        self.response_status = status.HTTP_200_OK
        return self.response


@extend_schema(
    tags=["Chatbot"],
    summary="Retrieve chat session details",
    description="""
    Retrieve a single chat session and its messages. Only accessible to the \
session owner (authenticated user or anonymous session).
    """,
    responses={
        200: ChatSessionDetailSerializer,
        404: OpenApiResponse(description="Chat session not found."),
        403: OpenApiResponse(description="Not allowed for this user/session."),
    },
)
class ChatSessionDetailView(PublicGetAPIView):
    """Retrieve a single chat session with its messages."""

    serializer_class = ChatSessionDetailSerializer
    permission_classes = [AllowAny]

    def get(self, request, session_id):
        filters = {"id": session_id, "is_active": True}
        if request.user.is_authenticated:
            filters["user"] = request.user
        else:
            if not request.session.session_key:
                return self.permission_denied(request, message="Not allowed.")
            filters.update(
                {"user": None, "session_key": request.session.session_key}
            )

        try:
            session_qs = ChatSession.objects.prefetch_related(
                Prefetch(
                    "messages",
                    queryset=ChatMessage.objects.order_by("created_at")
                )
            ).annotate(
                last_msg_at=Max("messages__created_at")
            )
            session = get_object_or_404(session_qs, **filters)

        except Http404:
            return Response(
                {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(session)
        self.response_data = serializer.data
        self.response_status = status.HTTP_200_OK
        return self.response
