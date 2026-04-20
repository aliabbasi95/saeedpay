# tickets/api/public/v1/schema/ticket.py

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from tickets.api.public.v1.serializers import TicketMessageSerializer
from tickets.utils.choices import TicketPriority, TicketStatus

TICKETS_TAG = "Support · Tickets"
TICKET_MESSAGES_TAG = "Support · Tickets · Messages"

ticket_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=[TICKETS_TAG],
        summary="List current user's tickets",
        description=(
            "Return the authenticated user's tickets with optional filtering "
            "and ordering."
        ),
        parameters=[
            OpenApiParameter(
                name="status",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by ticket status.",
                enum=[status.value for status in TicketStatus],
            ),
            OpenApiParameter(
                name="priority",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by ticket priority.",
                enum=[priority.value for priority in TicketPriority],
            ),
            OpenApiParameter(
                name="category",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by ticket category ID.",
            ),
            OpenApiParameter(
                name="ordering",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Example: `-created_at` or `priority`.",
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Ticket list returned successfully.",
                examples=[
                    OpenApiExample(
                        "ListResponse",
                        value=[
                            {
                                "id": 12,
                                "title": "Login issue",
                                "status": "open",
                                "priority": "high",
                                "category": {
                                    "id": 1,
                                    "name": "Technical",
                                    "description": "Technical support requests",
                                    "icon": "/media/tickets/icons/technical.svg",
                                    "color": "#2563eb",
                                },
                                "created_at": "2025-01-15T10:30:00Z",
                                "updated_at": "2025-01-15T10:30:00Z",
                            }
                        ],
                        response_only=True,
                    )
                ],
            )
        },
    ),
    create=extend_schema(
        tags=[TICKETS_TAG],
        summary="Create a ticket",
        description=(
            "Create a new ticket for the authenticated user. "
            "If `description` is provided, it will be stored as the first message. "
            "A user can have at most 15 open tickets."
        ),
        responses={
            201: OpenApiResponse(
                description="Ticket created successfully.",
                examples=[
                    OpenApiExample(
                        "CreatedResponse",
                        value={
                            "id": 15,
                            "title": "Payment failed",
                            "status": "open",
                            "priority": "normal",
                            "category": {
                                "id": 2,
                                "name": "Billing",
                                "description": "Payment and invoice related issues",
                                "icon": "/media/tickets/icons/billing.svg",
                                "color": "#10b981",
                            },
                            "created_at": "2025-01-15T11:00:00Z",
                            "updated_at": "2025-01-15T11:00:00Z",
                        },
                        response_only=True,
                    )
                ],
            ),
            400: OpenApiResponse(
                description="Validation error.",
                examples=[
                    OpenApiExample(
                        "ValidationError",
                        value={"category_id": ["This field is required."]},
                        response_only=True,
                    )
                ],
            ),
            429: OpenApiResponse(
                description="Too many open tickets.",
                examples=[
                    OpenApiExample(
                        "TooManyOpenTickets",
                        value={"non_field_errors": ["شما بیش از ۱۵ تیکت باز دارید."]},
                        response_only=True,
                    )
                ],
            ),
        },
        examples=[
            OpenApiExample(
                "CreateRequest",
                value={
                    "title": "مشکل پرداخت",
                    "description": "پرداخت ناموفق شد",
                    "priority": "normal",
                    "category_id": 2,
                },
                request_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        tags=[TICKETS_TAG],
        summary="Retrieve a ticket",
        description="Retrieve the details of a ticket owned by the current user.",
        responses={
            200: OpenApiResponse(
                description="Ticket retrieved successfully.",
                examples=[
                    OpenApiExample(
                        "RetrieveResponse",
                        value={
                            "id": 12,
                            "title": "Login issue",
                            "status": "open",
                            "priority": "high",
                            "category": {
                                "id": 1,
                                "name": "Technical",
                                "description": "Technical support requests",
                                "icon": "/media/tickets/icons/technical.svg",
                                "color": "#2563eb",
                            },
                            "created_at": "2025-01-15T10:30:00Z",
                            "updated_at": "2025-01-15T10:30:00Z",
                        },
                        response_only=True,
                    )
                ],
            ),
            404: OpenApiResponse(description="Ticket not found."),
        },
    ),
)

messages_list_schema = extend_schema(
    tags=[TICKET_MESSAGES_TAG],
    summary="List ticket messages",
    description="Return a paginated list of messages for the selected ticket.",
    responses={
        200: OpenApiResponse(
            response=TicketMessageSerializer(many=True),
            description="Paginated ticket messages returned successfully.",
            examples=[
                OpenApiExample(
                    "MessagesPage",
                    value={
                        "count": 1,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "ticket": 12,
                                "sender": "user",
                                "content": "سلام",
                                "reply_to": None,
                                "attachments": [],
                                "created_at": "2025-01-15T10:35:00Z",
                                "updated_at": "2025-01-15T10:35:00Z",
                            }
                        ],
                    },
                    response_only=True,
                )
            ],
        )
    },
)

add_message_schema = extend_schema(
    tags=[TICKET_MESSAGES_TAG],
    summary="Add a ticket message",
    description=(
        "Create a new message for the selected ticket. "
        "At most 2 attachments are allowed."
    ),
    request={
        "multipart/form-data": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "reply_to": {"type": "integer"},
                "files": {
                    "type": "array",
                    "items": {"type": "string", "format": "binary"},
                },
            },
            "required": ["content"],
        }
    },
    responses={
        201: OpenApiResponse(
            response=TicketMessageSerializer,
            description="Message created successfully.",
            examples=[
                OpenApiExample(
                    "CreatedMessage",
                    value={
                        "id": 2,
                        "ticket": 12,
                        "sender": "user",
                        "content": "مشکل پابرجاست",
                        "reply_to": None,
                        "attachments": [],
                        "created_at": "2025-01-15T10:40:00Z",
                        "updated_at": "2025-01-15T10:40:00Z",
                    },
                    response_only=True,
                )
            ],
        ),
        400: OpenApiResponse(
            description="Validation error.",
            examples=[
                OpenApiExample(
                    "TooManyFiles",
                    value={"files": ["حداکثر ۲ فایل می‌توانید ارسال کنید."]},
                    response_only=True,
                ),
                OpenApiExample(
                    "InvalidReply",
                    value={"reply_to": ["پیام ارجاع باید متعلق به همین تیکت باشد."]},
                    response_only=True,
                ),
            ],
        ),
        404: OpenApiResponse(description="Ticket not found."),
    },
    examples=[
        OpenApiExample(
            "AddMessageRequest",
            value={
                "content": "مشکل پابرجاست",
                "reply_to": 1,
            },
            request_only=True,
        )
    ],
)
