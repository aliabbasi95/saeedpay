# tickets/api/public/v1/schema.py
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    extend_schema, extend_schema_view,
    OpenApiParameter, OpenApiExample, OpenApiResponse,
)

from tickets.api.public.v1.serializers import TicketMessageSerializer
from tickets.utils.choices import TicketStatus, TicketPriority

# ---------- ViewSet (list/create/retrieve) ----------
ticket_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=["Tickets"],
        summary="لیست تیکت‌های کاربر",
        description="لیست تیکت‌های کاربر جاری با فیلتر/مرتب‌سازی.",
        parameters=[
            OpenApiParameter(
                name="status", type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="فیلتر بر اساس وضعیت",
                enum=[s.value for s in TicketStatus],
            ),
            OpenApiParameter(
                name="priority", type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="فیلتر بر اساس اولویت",
                enum=[p.value for p in TicketPriority],
            ),
            OpenApiParameter(
                name="category", type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="شناسه دسته‌بندی",
            ),
            OpenApiParameter(
                name="ordering", type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="مثال: -created_at | priority",
            ),
        ],
        responses={200: OpenApiResponse(description="OK")},
        examples=[
            OpenApiExample(
                "نمونه پاسخ",
                value=[{
                    "id": 12, "title": "Login issue", "status": "open",
                    "priority": "high",
                    "category": {"id": 1, "name": "Technical"},
                    "created_at": "2025-01-15T10:30:00Z",
                    "updated_at": "2025-01-15T10:30:00Z",
                }],
                response_only=True,
            )
        ],
    ),
    create=extend_schema(
        tags=["Tickets"],
        summary="ایجاد تیکت جدید",
        description="ایجاد تیکت؛ اگر فیلد `description` ارسال شود به عنوان اولین پیام ذخیره می‌گردد. محدودیت: حداکثر ۱۵ تیکت باز.",
        responses={
            201: OpenApiResponse(description="Created"),
            400: OpenApiResponse(description="Validation error"),
            429: OpenApiResponse(description="Too many open tickets"),
        },
        examples=[
            OpenApiExample(
                "نمونه درخواست",
                value={
                    "title": "مشکل پرداخت", "description": "پرداخت ناموفق شد",
                    "priority": "normal", "category_id": 2
                },
                request_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        tags=["Tickets"],
        summary="جزئیات تیکت",
        description="جزئیات یک تیکت (فقط مالک).",
        responses={
            200: OpenApiResponse(description="OK"),
            404: OpenApiResponse(description="Not found")
        },
    ),
)

# ---------- /messages (GET) ----------
messages_list_schema = extend_schema(
    tags=["Tickets · Messages"],
    summary="لیست پیام‌های تیکت",
    description="صفحه‌بندی پیام‌های یک تیکت.",
    responses={
        200: OpenApiResponse(
            response=TicketMessageSerializer(many=True),
            description="OK",
            examples=[OpenApiExample(
                "نمونه صفحه",
                value={
                    "count": 1, "results": [
                        {"id": 1, "content": "سلام", "sender": "user"}]
                },
                response_only=True,
            )],
        )
    },
)

# ---------- /messages (POST) ----------
add_message_schema = extend_schema(
    tags=["Tickets · Messages"],
    summary="افزودن پیام",
    description="ارسال پیام جدید برای یک تیکت (حداکثر ۲ فایل پیوست).",
    request={
        "multipart/form-data": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "reply_to": {"type": "integer"},
                "files": {
                    "type": "array",
                    "items": {"type": "string", "format": "binary"}
                },
            },
            "required": ["content"],
        }
    },
    responses={
        201: OpenApiResponse(
            response=TicketMessageSerializer, description="Created"
        ),
        400: OpenApiResponse(description="Validation error"),
        404: OpenApiResponse(description="Ticket not found"),
    },
    examples=[
        OpenApiExample(
            "موفق", value={
                "id": 2, "content": "مشکل پابرجاست", "sender": "user"
            }, response_only=True
        ),
        OpenApiExample(
            "خطا - تعداد فایل", value={"files": ["حداکثر 2 فایل مجاز است"]},
            response_only=True, status_codes=["400"]
        ),
    ],
)
