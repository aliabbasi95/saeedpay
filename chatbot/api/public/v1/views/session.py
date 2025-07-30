from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny

from lib.cas_auth.views import PublicGetAPIView
from chatbot.models import ChatSession, ChatMessage


class UserChatSessionsView(PublicGetAPIView):
    """List chat sessions belonging to the current user (or anonymous session)."""

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
                    ChatSession, id=session_id, user=None, session_key=session_key
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