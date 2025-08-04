from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, OpenApiResponse

from lib.cas_auth.views import PublicGetAPIView
from chatbot.models import ChatSession, ChatMessage


@extend_schema(
    tags=["chatbot"],
    summary="List user chat sessions",
    description="""
    List chat sessions belonging to the current user (if authenticated) or \
the current anonymous session (if not authenticated). Sessions are ordered by \
creation time descending.
    """,
    responses={
        200: OpenApiResponse(
            description=(
                "A list of chat sessions for the user or anonymous session."
            ),
            response={
                "type": "object",
                "properties": {
                    "sessions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "session_id": {
                                    "type": "integer",
                                    "description": "Session ID",
                                },
                                "created_at": {
                                    "type": "string",
                                    "format": "date-time",
                                    "description": (
                                        "Session creation timestamp"
                                    ),
                                },
                                "is_active": {
                                    "type": "boolean",
                                    "description": (
                                        "Whether the session is active"
                                    ),
                                },
                            },
                        },
                    },
                },
            },
        ),
        403: OpenApiResponse(description="Not allowed for this user/session."),
    },
)
class UserChatSessionsView(PublicGetAPIView):
    """
    List chat sessions belonging to the current user (or anonymous session).
    """

    serializer_class = serializers.Serializer
    permission_classes = [AllowAny]

    def get(self, request):
        if request.user.is_authenticated:
            sessions = ChatSession.objects.filter(user=request.user).order_by(
                "-created_at"
            )
        else:
            session_key = request.session.session_key
            if not session_key:
                sessions = ChatSession.objects.none()
            else:
                sessions = ChatSession.objects.filter(
                    user=None, session_key=session_key
                ).order_by("-created_at")

        self.response_data = {
            "sessions": [
                {
                    "session_id": s.id,
                    "created_at": s.created_at,
                    "is_active": s.is_active,
                }
                for s in sessions
            ]
        }
        self.response_status = status.HTTP_200_OK
        return self.response


@extend_schema(
    tags=["chatbot"],
    summary="Retrieve chat session details",
    description="""
    Retrieve a single chat session and its messages. Only accessible to the \
session owner (authenticated user or anonymous session).
    """,
    responses={
        200: OpenApiResponse(
            description="Chat session details with messages.",
            response={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "integer",
                        "description": "Session ID",
                    },
                    "created_at": {
                        "type": "string",
                        "format": "date-time",
                        "description": "Session creation timestamp",
                    },
                    "is_active": {
                        "type": "boolean",
                        "description": "Whether the session is active",
                    },
                    "messages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sender": {
                                    "type": "string",
                                    "description": "Sender (user or ai)",
                                },
                                "content": {
                                    "type": "string",
                                    "description": "Message content",
                                },
                                "created_at": {
                                    "type": "string",
                                    "format": "date-time",
                                    "description": (
                                        "Message creation timestamp"
                                    ),
                                },
                            },
                        },
                    },
                },
            },
        ),
        404: OpenApiResponse(description="Chat session not found."),
        403: OpenApiResponse(description="Not allowed for this user/session."),
    },
)
class ChatSessionDetailView(PublicGetAPIView):
    """Retrieve a single chat session with its messages."""

    serializer_class = serializers.Serializer
    permission_classes = [AllowAny]

    def get(self, request, session_id):
        try:
            if request.user.is_authenticated:
                session = get_object_or_404(
                    ChatSession, id=session_id, user=request.user
                )
            else:
                session_key = request.session.session_key
                if not session_key:
                    return self.permission_denied(
                        request, message="Not allowed."
                    )
                session = get_object_or_404(
                    ChatSession,
                    id=session_id,
                    user=None,
                    session_key=session_key,
                )
        except Http404:
            from rest_framework.response import Response

            return Response(
                {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )

        messages = ChatMessage.objects.filter(session=session).order_by(
            "created_at"
        )
        self.response_data = {
            "session_id": session.id,
            "created_at": session.created_at,
            "is_active": session.is_active,
            "messages": [
                {
                    "sender": m.sender,
                    "content": m.message,
                    "created_at": m.created_at,
                }
                for m in messages
            ],
        }
        self.response_status = status.HTTP_200_OK
        return self.response
