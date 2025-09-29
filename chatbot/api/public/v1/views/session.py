# chatbot/api/public/v1/views/session.py
# ViewSet for chat sessions: list/retrieve/create + chat action (LLM proxy)

import logging
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.db.models import Max, F, Prefetch
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
    OpenApiExample,
)
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from chatbot.api.public.v1.serializers import (
    ChatSessionSerializer,
    ChatSessionDetailSerializer,
    ChatRequestSerializer,
    ChatResponseSerializer,
    ChatMessageSerializer,
)
from chatbot.models import ChatSession, ChatMessage

logger = logging.getLogger(__name__)

LLM_BASE_URL = getattr(settings, "LLM_BASE_URL", "http://localhost:8001")
HISTORY_LIMIT = getattr(settings, "CHATBOT_HISTORY_LIMIT", 4)
SESSION_LIMIT_ANONYMOUS = getattr(settings, "CHATBOT_SESSION_LIMIT", 2)


@extend_schema(tags=["Chatbot"])
class ChatSessionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet
):
    """
    list:     User's chat sessions (or current anonymous session), newest first.
    retrieve: A single session with its messages (ordered asc).
    create:   Start a new chat session (enforces anonymous session limit).
    chat:     POST /sessions/{id}/chat/ → send a message to LLM, persists Q/A.
    """
    permission_classes = [AllowAny]
    lookup_field = "pk"

    # ---------- queryset / serializer selection ----------

    def get_queryset(self):
        """Scope sessions to the authenticated user or the current anonymous session."""
        request = self.request
        if request.user.is_authenticated:
            base_qs = ChatSession.objects.filter(user=request.user)
        else:
            session_key = request.session.session_key
            if not session_key:
                return ChatSession.objects.none()
            base_qs = ChatSession.objects.filter(
                user=None, session_key=session_key
            )

        # list: annotate last activity for ordering
        if self.action == "list":
            return (
                base_qs
                .annotate(last_msg_at=Max("messages__created_at"))
                .annotate(
                    last_sort_at=Coalesce(F("last_msg_at"), F("created_at"))
                )
                .order_by("-last_sort_at")
            )

        # retrieve: prefetch messages ascending
        if self.action == "retrieve":
            return (
                base_qs
                .prefetch_related(
                    Prefetch(
                        "messages", queryset=ChatMessage.objects.order_by(
                            "created_at"
                        )
                    )
                )
                .annotate(last_msg_at=Max("messages__created_at"))
            )

        # chat/create: simple base
        return base_qs

    def get_serializer_class(self):
        if self.action == "list":
            return ChatSessionSerializer
        if self.action == "retrieve":
            return ChatSessionDetailSerializer
        if self.action == "chat":
            return ChatRequestSerializer
        return ChatSessionSerializer  # for create response payload

    # ---------- create (start session) ----------

    @extend_schema(
        summary="Start a new chat session",
        description="Create a new chat session; anonymous users are limited by CHATBOT_SESSION_LIMIT.",
        responses={
            201: OpenApiResponse(
                description="Chat session created successfully",
                response=ChatSessionSerializer,
                examples=[
                    OpenApiExample("OK", value={"id": 1, "is_active": True})],
            ),
            403: OpenApiResponse(
                description="Anonymous session limit reached"
            ),
        },
    )
    def create(self, request, *args, **kwargs):
        user = request.user if request.user.is_authenticated else None

        # Ensure we have a session key for anonymous tracking
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key

        # Enforce anonymous session limit
        if user is None:
            existing = ChatSession.objects.filter(
                user=None, session_key=session_key
            ).count()
            if existing >= SESSION_LIMIT_ANONYMOUS:
                return Response(
                    {
                        "detail": f"Anonymous users are limited to {SESSION_LIMIT_ANONYMOUS} chat sessions. "
                                  f"Please log in to continue chatting."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Client IP extraction
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        ip_address = (
            xff.split(",")[0] if xff else request.META.get("REMOTE_ADDR"))

        session = ChatSession.objects.create(
            user=user,
            session_key=session_key,
            ip_address=ip_address,
            is_active=True,
        )
        return Response(
            ChatSessionSerializer(session).data, status=status.HTTP_201_CREATED
        )

    # ---------- chat action ----------

    @extend_schema(
        summary="Send message to AI chatbot",
        description=(
                "Send a message to the AI chatbot; maintains session-scoped history. "
                f"History window is limited to last {HISTORY_LIMIT} messages."),
        request=ChatRequestSerializer,
        responses={
            200: ChatResponseSerializer,
            400: OpenApiResponse(description="Bad request - invalid input"),
            403: OpenApiResponse(
                description="Anonymous limit reached or not allowed"
            ),
            404: OpenApiResponse(description="Chat session not found"),
            502: OpenApiResponse(description="LLM service error"),
        },
    )
    @action(detail=True, methods=["post"], url_path="chat")
    def chat(self, request, *args, **kwargs):
        """Proxy the user message to the LLM service and return its answer; persists both sides."""
        # Access control: only owner (user) or current anonymous session can use this session
        session = get_object_or_404(
            self.get_queryset(), id=kwargs.get("pk"), is_active=True
        )

        # Validate payload
        ser = ChatRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        query = ser.validated_data["query"]

        # Anonymous message limit
        if not request.user.is_authenticated:
            user_message_count = ChatMessage.objects.filter(
                session=session, sender="user"
            ).count()
            if user_message_count >= HISTORY_LIMIT:
                return Response(
                    {
                        "detail": f"Anonymous users are limited to {HISTORY_LIMIT} messages per session. "
                                  f"Please log in to continue chatting."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Build rolling history (oldest→newest)
        msgs = list(
            ChatMessage.objects.filter(session=session).order_by(
                "-created_at"
            )[:HISTORY_LIMIT]
        )
        msgs.reverse()
        history = [
            {
                "content": m.message,
                "role": "user" if m.sender == "user" else "assistant",
            }
            for m in msgs
        ]

        # Persist user message
        ChatMessage.objects.create(
            session=session, sender="user", message=query
        )

        payload = {"history": history, "query": query}

        try:
            llm_url = urljoin(LLM_BASE_URL.rstrip("/") + "/", "api/v1/chat")
            resp = requests.post(llm_url, json=payload, timeout=30)
            resp.raise_for_status()

            # Extract answer (json or plain)
            answer = None
            try:
                data = resp.json()
                answer = data.get("answer") or data.get("content") or data.get(
                    "response"
                )
            except ValueError:
                pass
            if not answer:
                answer = (resp.text or "").strip()
            if not answer:
                raise ValueError("No answer in LLM response")

            # Persist AI response
            ChatMessage.objects.create(
                session=session, sender="ai", message=answer
            )

            out = ChatResponseSerializer(data={"answer": answer})
            out.is_valid(raise_exception=True)
            return Response(out.data, status=status.HTTP_200_OK)

        except Exception as exc:
            logger.exception("LLM proxy error")
            return Response(
                {"detail": f"LLM error: {str(exc)}"},
                status=status.HTTP_502_BAD_GATEWAY
            )

    # ---------- optional: messages listing per session ----------

    @extend_schema(
        summary="List messages of a session",
        responses={200: ChatMessageSerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="messages")
    def messages(self, request, *args, **kwargs):
        """Return session messages ordered ascending (useful for lightweight views)."""
        session = get_object_or_404(
            self.get_queryset(), id=kwargs.get("pk"), is_active=True
        )
        qs = session.messages.order_by("created_at")
        return Response(
            ChatMessageSerializer(qs, many=True).data,
            status=status.HTTP_200_OK
        )
