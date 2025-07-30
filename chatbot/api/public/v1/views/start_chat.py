from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.conf import settings

from chatbot.models import ChatSession
from lib.cas_auth.views import PublicAPIView


# Maximum number of chat sessions an anonymous user can create.
SESSION_LIMIT_ANONYMOUS = getattr(settings, "CHATBOT_SESSION_LIMIT", 2)


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
    """API view that creates a new chat session."""

    serializer_class = serializers.Serializer
    permission_classes = [AllowAny]

    def post(self, request):
        # Determine the user (None for anonymous users)
        user = request.user if request.user.is_authenticated else None

        # Enforce anonymous session creation limit
        if user is None:
            # Ensure session key exists so we can track the anonymous user
            if not request.session.session_key:
                request.session.create()
            session_key = request.session.session_key

            existing_sessions = ChatSession.objects.filter(
                session_key=session_key, user=None
            ).count()

            if existing_sessions >= SESSION_LIMIT_ANONYMOUS:
                self.response_data = {
                    "detail": (
                        "Anonymous users are limited to "
                        f"{SESSION_LIMIT_ANONYMOUS} chat sessions. "
                        "Please log in or register to continue chatting."
                    )
                }
                self.response_status = status.HTTP_403_FORBIDDEN
                return self.response

        # Ensure session exists and retrieve the session key (already created above for anonymous)
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key

        # Extract client IP address
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        ip_address = (
            x_forwarded_for.split(",")[0]
            if x_forwarded_for
            else request.META.get("REMOTE_ADDR")
        )

        # Create the chat session
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