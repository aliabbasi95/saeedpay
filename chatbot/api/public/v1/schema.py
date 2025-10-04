# chatbot/api/public/v1/schema.py

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiResponse,
    OpenApiExample,
    OpenApiParameter,
    OpenApiTypes,
)
from rest_framework import status

from chatbot.api.public.v1.serializers import (
    ChatSessionSerializer,
    ChatSessionDetailSerializer,
    ChatRequestSerializer,
    ChatResponseSerializer,
    ChatMessageSerializer,
)

# -------- ViewSet (list/retrieve/create) --------
chat_session_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=["Chatbot · Sessions"],
        summary="List chat sessions",
        description=(
            "Return chat sessions for current user; if anonymous, returns current session "
            "by session_key. Ordered by last activity."
        ),
        responses={200: ChatSessionSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["Chatbot · Sessions"],
        summary="Get a chat session with messages",
        parameters=[
            OpenApiParameter(
                name="id", type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description="Chat session id"
            )
        ],
        responses={200: ChatSessionDetailSerializer},
    ),
    create=extend_schema(
        tags=["Chatbot · Sessions"],
        summary="Start a new chat session",
        description="Create a chat session. Anonymous users are limited by server settings.",
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                response=ChatSessionSerializer,
                description="Session created",
                examples=[OpenApiExample(
                    "Created",
                    value={
                        "id": 12, "is_active": True, "session_key": "abc123"
                    },
                    response_only=True,
                    status_codes=[str(status.HTTP_201_CREATED)],
                )],
            ),
            status.HTTP_403_FORBIDDEN: OpenApiResponse(
                description="Anonymous session limit reached"
            ),
        },
    ),
)

# -------- Actions (chat, messages) --------
chat_action_schema = extend_schema(
    tags=["Chatbot · Talk"],
    summary="Send a message to chatbot",
    description=(
        "Proxy user message to LLM with a rolling history window; persists both user and assistant messages. "
        "Returns the assistant's answer."
    ),
    request=ChatRequestSerializer,
    responses={
        200: ChatResponseSerializer,
        400: OpenApiResponse(description="Invalid input"),
        403: OpenApiResponse(
            description="Anonymous limits reached or forbidden"
        ),
        404: OpenApiResponse(description="Session not found"),
        502: OpenApiResponse(description="LLM gateway error"),
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
    tags=["Chatbot · Sessions"],
    summary="List messages of a session",
    parameters=[
        OpenApiParameter(
            name="id", type=OpenApiTypes.INT, location=OpenApiParameter.PATH,
            description="Chat session id"
        )
    ],
    responses={200: ChatMessageSerializer(many=True)},
)
