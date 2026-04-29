# apps/chatbot/api/public/v1/views/session.py

import logging
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.db.models import F, Max, Prefetch
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.chatbot.api.public.v1.schema import (
    chat_action_schema,
    chat_session_viewset_schema,
    messages_action_schema,
)
from apps.chatbot.api.public.v1.serializers import (
    ChatMessageSerializer,
    ChatRequestSerializer,
    ChatResponseSerializer,
    ChatSessionDetailSerializer,
    ChatSessionSerializer,
)
from apps.chatbot.models import ChatMessage, ChatSession
from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin

logger = logging.getLogger(__name__)

LLM_BASE_URL = getattr(settings, "LLM_BASE_URL", "http://localhost:8001")
HISTORY_LIMIT = getattr(settings, "CHATBOT_HISTORY_LIMIT", 4)
SESSION_LIMIT_ANONYMOUS = getattr(settings, "CHATBOT_SESSION_LIMIT", 2)


@chat_session_viewset_schema
class ChatSessionViewSet(
    ScopedThrottleByActionMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Read/write endpoints for chat sessions plus chat and messages actions."""

    permission_classes = [AllowAny]
    pagination_class = None
    lookup_field = "pk"
    lookup_value_regex = r"\d+"

    throttle_scope_map = {
        "default": "chat-sessions",
        "create": "chat-start",
        "chat": "chat-talk",
        "messages": "chat-messages",
    }

    def get_queryset(self):
        """Scope sessions to the authenticated user or the current anonymous session."""
        if getattr(self, "swagger_fake_view", False):
            return ChatSession.objects.none()

        request = self.request
        if request.user.is_authenticated:
            base_qs = ChatSession.objects.filter(user=request.user)
        else:
            if not request.session.session_key:
                return ChatSession.objects.none()
            base_qs = ChatSession.objects.filter(
                user=None,
                session_key=request.session.session_key,
            )

        if self.action == "list":
            return (
                base_qs.annotate(last_msg_at=Max("messages__created_at"))
                .annotate(last_sort_at=Coalesce(F("last_msg_at"), F("created_at")))
                .order_by("-last_sort_at")
            )

        if self.action == "retrieve":
            return base_qs.prefetch_related(
                Prefetch(
                    "messages",
                    queryset=ChatMessage.objects.order_by("created_at"),
                )
            ).annotate(last_msg_at=Max("messages__created_at"))

        return base_qs

    def get_serializer_class(self):
        if self.action == "list":
            return ChatSessionSerializer
        if self.action == "retrieve":
            return ChatSessionDetailSerializer
        if self.action == "chat":
            return ChatRequestSerializer
        return ChatSessionSerializer

    def create(self, request, *args, **kwargs):
        """Start a chat session and enforce anonymous session limits."""
        user = request.user if request.user.is_authenticated else None

        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key

        if user is None:
            existing = ChatSession.objects.filter(
                user=None,
                session_key=session_key,
            ).count()
            if existing >= SESSION_LIMIT_ANONYMOUS:
                return Response(
                    {
                        "detail": (
                            f"Anonymous users are limited to "
                            f"{SESSION_LIMIT_ANONYMOUS} sessions. Please log in to "
                            f"continue chatting."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        ip_address = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0]
        ip_address = ip_address or request.META.get("REMOTE_ADDR")

        session = ChatSession.objects.create(
            user=user,
            session_key=session_key,
            ip_address=ip_address,
            is_active=True,
        )
        return Response(
            ChatSessionSerializer(session).data,
            status=status.HTTP_201_CREATED,
        )

    @chat_action_schema
    @action(detail=True, methods=["post"], url_path="chat")
    def chat(self, request, *args, **kwargs):
        """Proxy the user message to LLM and persist both user and AI messages."""
        session = get_object_or_404(
            self.get_queryset(),
            id=kwargs.get("pk"),
            is_active=True,
        )

        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        query = serializer.validated_data["query"]

        if not request.user.is_authenticated:
            user_message_count = ChatMessage.objects.filter(
                session=session,
                sender="user",
            ).count()
            if user_message_count >= HISTORY_LIMIT:
                return Response(
                    {
                        "detail": (
                            f"Anonymous users are limited to {HISTORY_LIMIT} messages "
                            f"per session. Please log in to continue chatting."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        messages = list(
            ChatMessage.objects.filter(session=session).order_by("-created_at")[
                :HISTORY_LIMIT
            ]
        )
        messages.reverse()
        history = [
            {
                "content": message.message,
                "role": "user" if message.sender == "user" else "assistant",
            }
            for message in messages
        ]

        ChatMessage.objects.create(session=session, sender="user", message=query)

        try:
            llm_url = urljoin(LLM_BASE_URL.rstrip("/") + "/", "api/v1/chat")
            response = requests.post(
                llm_url,
                json={"history": history, "query": query},
                timeout=30,
            )
            response.raise_for_status()

            try:
                data = response.json()
                answer = (
                    data.get("answer") or data.get("content") or data.get("response")
                )
            except ValueError:
                answer = (response.text or "").strip()

            if not answer:
                raise ValueError("No answer in LLM response")

            ChatMessage.objects.create(session=session, sender="ai", message=answer)

            output = ChatResponseSerializer(data={"answer": answer})
            output.is_valid(raise_exception=True)
            return Response(output.data, status=status.HTTP_200_OK)

        except Exception as exc:
            logger.exception("LLM proxy error")
            return Response(
                {"detail": f"LLM error: {str(exc)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

    @messages_action_schema
    @action(detail=True, methods=["get"], url_path="messages")
    def messages(self, request, *args, **kwargs):
        """Return session messages ordered by creation time ascending."""
        session = get_object_or_404(
            self.get_queryset(),
            id=kwargs.get("pk"),
            is_active=True,
        )
        queryset = session.messages.order_by("created_at")
        return Response(
            ChatMessageSerializer(queryset, many=True).data,
            status=status.HTTP_200_OK,
        )
