import requests
from django.conf import settings
from rest_framework import status
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated, AllowAny
from lib.cas_auth.views import PublicAPIView, PublicGetAPIView
from chatbot.models import ChatSession, ChatMessage
from chatbot.serializers import ChatRequestSerializer, ChatResponseSerializer
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.http import Http404

LLM_BASE_URL = getattr(settings, "LLM_BASE_URL", "http://localhost:8001")
HISTORY_LIMIT = getattr(settings, "CHATBOT_HISTORY_LIMIT", 4)


@extend_schema(
    tags=["chatbot"],
    summary="Start a new chat session",
    description="""
    Create a new chat session for communicating with the AI chatbot.
    If the user is authenticated, the session will be associated with the user.
    If the user is not authenticated, the session will be associated with the 
    session key.
    If the session key is not found, the session will be created with the user 
    set to None.
    """,
    responses={
        201: OpenApiResponse(
            description="Chat session created successfully",
            response={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "integer",
                        "description": "The ID of the created chat session",
                    },
                    "created_at": {
                        "type": "string",
                        "format": "date-time",
                        "description": "Session creation timestamp",
                    },
                },
            },
        )
    },
)
class StartChatView(PublicAPIView):
    serializer_class = serializers.Serializer
    permission_classes = [AllowAny]

    def post(self, request):
        # Handle user assignment properly (None for anonymous users)
        user = request.user if request.user.is_authenticated else None

        # Ensure session exists and get session key
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key

        # Get client IP address
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        ip_address = (
            x_forwarded_for.split(",")[0]
            if x_forwarded_for
            else request.META.get("REMOTE_ADDR")
        )

        # Create session with proper values
        session = ChatSession.objects.create(
            user=user,
            session_key=session_key,
            ip_address=ip_address,
            is_active=True,
        )

        # Prepare response
        self.response_data = {
            "session_id": session.id,
            "created_at": session.created_at,
        }
        self.response_status = status.HTTP_201_CREATED
        return self.response


@extend_schema(
    tags=["chatbot"],
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
    """
    Chat endpoint for sending messages to the AI chatbot.

    This endpoint allows users to send messages to the AI chatbot and receive
    responses.

    The conversation history is maintained within the session context.
    """

    serializer_class = ChatRequestSerializer
    permission_classes = [AllowAny]

    def post(self, request, session_id):
        """
        Send a message to the AI chatbot and receive a response.

        Args:
            request: The HTTP request containing the user's message
            session_id: The ID of the chat session

        Returns:
            JSON response containing the AI's answer
        """
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

        # Validate input using serializer
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            self.response_data = serializer.errors
            self.response_status = status.HTTP_400_BAD_REQUEST
            return self.response

        # Message limit for anonymous users
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
        # Fetch last N messages
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
        payload = {"history": history, "query": query}
        # Save user message
        ChatMessage.objects.create(
            session=session, sender="user", message=query
        )
        # Proxy to LLM
        try:
            resp = requests.post(
                f"{LLM_BASE_URL}api/v1/chat", json=payload, timeout=30
            )
            resp.raise_for_status()
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
                # If not JSON, treat as plain text
                answer = resp.text.strip()
                if not answer:
                    raise ValueError("No answer in LLM response")
            # Save AI message
            ChatMessage.objects.create(
                session=session, sender="ai", message=answer
            )
            response_serializer = ChatResponseSerializer(
                data={"answer": answer}
            )
            response_serializer.is_valid(raise_exception=True)
            self.response_data = response_serializer.data
            self.response_status = status.HTTP_200_OK
        except Exception as e:
            self.response_data = {"detail": f"LLM error: {str(e)}"}
            self.response_status = status.HTTP_502_BAD_GATEWAY
        return self.response


class UserChatSessionsView(PublicGetAPIView):
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
