import requests
from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.permissions import AllowAny

from chatbot.api.public.v1.serializers import (
    ChatRequestSerializer,
    ChatResponseSerializer,
)
from chatbot.models import ChatSession, ChatMessage
from lib.cas_auth.views import PublicAPIView

LLM_BASE_URL = getattr(settings, "LLM_BASE_URL", "http://localhost:8001")
HISTORY_LIMIT = getattr(settings, "CHATBOT_HISTORY_LIMIT", 4)


@extend_schema(
    tags=["Chatbot"],
    summary="Send message to AI chatbot",
    description=(
        "Send a message to the AI chatbot and receive a response. "
        "The conversation history is maintained within the session context."
    ),
    request=ChatRequestSerializer,
    responses={
        200: ChatResponseSerializer,
        400: OpenApiResponse(description="Bad request - Invalid input data"),
        404: OpenApiResponse(description="Chat session not found"),
        502: OpenApiResponse(description="LLM service error"),
    },
)
class ChatView(PublicAPIView):
    """Endpoint for interacting with the AI chatbot within a session."""

    serializer_class = ChatRequestSerializer
    permission_classes = [AllowAny]

    def post(self, request, session_id):
        """Proxy the user message to the LLM service and return its answer."""
        user = request.user if request.user.is_authenticated else None

        try:
            session = get_object_or_404(
                ChatSession, id=session_id, user=user, is_active=True
            )
        except Http404:
            from rest_framework.response import Response

            return Response(
                {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Validate input
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            self.response_data = serializer.errors
            self.response_status = status.HTTP_400_BAD_REQUEST
            return self.response

        # Enforce anonymous user message limit
        if user is None:
            user_message_count = ChatMessage.objects.filter(
                session=session, sender="user"
            ).count()
            if user_message_count >= HISTORY_LIMIT:
                self.response_data = {
                    "detail": (
                        f"Anonymous users are limited to "
                        f"{HISTORY_LIMIT} messages per session. "
                        "Please log in to continue chatting."
                    )
                }
                self.response_status = status.HTTP_403_FORBIDDEN
                return self.response

        query = serializer.validated_data["query"]

        # Retrieve last N messages ordered ascending
        messages = ChatMessage.objects.filter(session=session).order_by(
            "-created_at"
        )[:HISTORY_LIMIT][::-1]
        history = [
            {
                "content": m.message,
                "role": "user" if m.sender == "user" else "assistant",
            }
            for m in messages
        ]

        # Persist the user message
        ChatMessage.objects.create(
            session=session, sender="user", message=query
        )

        payload = {"history": history, "query": query}

        # Proxy the request to LLM backend
        try:
            resp = requests.post(
                f"{LLM_BASE_URL}api/v1/chat", json=payload, timeout=30
            )
            resp.raise_for_status()

            # Extract answer depending on json/plain-text structure
            try:
                data = resp.json()
                answer = (
                    data.get("answer")
                    or data.get("content")
                    or data.get("response")
                )
                if not answer:
                    raise ValueError("No answer in LLM response")
            except ValueError:
                # Fallback to plain text
                answer = resp.text.strip()
                if not answer:
                    raise ValueError("No answer in LLM response")

            # Save AI response
            ChatMessage.objects.create(
                session=session, sender="ai", message=answer
            )

            response_serializer = ChatResponseSerializer(
                data={"answer": answer}
            )
            response_serializer.is_valid(raise_exception=True)
            self.response_data = response_serializer.data
            self.response_status = status.HTTP_200_OK
        except Exception as exc:
            self.response_data = {"detail": f"LLM error: {str(exc)}"}
            self.response_status = status.HTTP_502_BAD_GATEWAY

        return self.response
