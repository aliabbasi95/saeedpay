# chatbot/api/public/v1/schema/session.py

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status

from chatbot.api.public.v1.serializers import (
    ChatMessageSerializer,
    ChatRequestSerializer,
    ChatResponseSerializer,
    ChatSessionDetailSerializer,
    ChatSessionSerializer,
)

CHATBOT_TAG = "Support · Chatbot"

chat_session_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=[CHATBOT_TAG],
        summary="List chat sessions",
        description=(
            "Return chat sessions for the current user. For anonymous users, only "
            "sessions tied to the current session key are returned. Results are "
            "ordered by latest activity."
        ),
        responses={200: ChatSessionSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=[CHATBOT_TAG],
        summary="Retrieve a chat session with messages",
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description="Chat session ID.",
            )
        ],
        responses={200: ChatSessionDetailSerializer},
    ),
    create=extend_schema(
        tags=[CHATBOT_TAG],
        summary="Start a new chat session",
        description=(
            "Create a new chat session. Anonymous users are limited by server-side "
            "session limits."
        ),
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                response=ChatSessionSerializer,
                description="Session created successfully.",
                examples=[
                    OpenApiExample(
                        "Created",
                        value={
                            "id": 12,
                            "user": None,
                            "session_key": "abc123",
                            "ip_address": "127.0.0.1",
                            "is_active": True,
                            "created_at": "2025-01-01T12:00:00Z",
                            "last_activity_at": "2025-01-01T12:00:00Z",
                        },
                        response_only=True,
                        status_codes=[str(status.HTTP_201_CREATED)],
                    )
                ],
            ),
            status.HTTP_403_FORBIDDEN: OpenApiResponse(
                description="Anonymous session limit reached.",
            ),
        },
    ),
)

chat_action_schema = extend_schema(
    tags=[CHATBOT_TAG],
    summary="Send a message to the chatbot",
    description=(
        "Send a user message to the chatbot service, persist the conversation, "
        "and return the assistant response."
    ),
    request=ChatRequestSerializer,
    responses={
        200: ChatResponseSerializer,
        400: OpenApiResponse(description="Invalid request payload."),
        403: OpenApiResponse(description="Anonymous usage limit reached."),
        404: OpenApiResponse(description="Session not found."),
        502: OpenApiResponse(description="LLM gateway error."),
    },
    examples=[
        OpenApiExample(
            "Request",
            value={"query": "What's my last order status?"},
            request_only=True,
        ),
        OpenApiExample(
            "Response",
            value={"answer": "Your last order #A123 is out for delivery."},
            response_only=True,
            status_codes=[str(status.HTTP_200_OK)],
        ),
    ],
)

messages_action_schema = extend_schema(
    tags=[CHATBOT_TAG],
    summary="List messages of a chat session",
    parameters=[
        OpenApiParameter(
            name="id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description="Chat session ID.",
        )
    ],
    responses={200: ChatMessageSerializer(many=True)},
)
