# tickets/api/public/v1/schema.py
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiExample,
    OpenApiResponse,
)
from drf_spectacular.types import OpenApiTypes

from tickets.utils.choices import TicketStatus, TicketPriority


# Ticket ViewSet Schema
ticket_viewset_schema = extend_schema_view(
    list=extend_schema(
        summary="لیست تیکت‌های کاربر",
        description="دریافت لیست تمام تیکت‌های متعلق به کاربر جاری با امکان فیلتر و مرتب‌سازی",
        tags=["Tickets"],
        parameters=[
            OpenApiParameter(
                name="status",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="فیلتر بر اساس وضعیت تیکت",
                enum=[status.value for status in TicketStatus],
                many=True,
                examples=[
                    OpenApiExample(
                        "فیلتر وضعیت باز",
                        value="open",
                    ),
                    OpenApiExample(
                        "فیلتر چند وضعیت",
                        value=["open", "in_progress"],
                    ),
                ],
            ),
            OpenApiParameter(
                name="priority",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="فیلتر بر اساس اولویت تیکت",
                enum=[priority.value for priority in TicketPriority],
                examples=[
                    OpenApiExample(
                        "فیلتر اولویت بالا",
                        value="high",
                    ),
                ],
            ),
            OpenApiParameter(
                name="category",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="فیلتر بر اساس دسته‌بندی تیکت",
                examples=[
                    OpenApiExample(
                        "فیلتر دسته‌بندی با ID 1",
                        value=1,
                    ),
                    OpenApiExample(
                        "بدون فیلتر دسته‌بندی",
                        value=None,
                        description="برای غیرفعال کردن فیلتر دسته‌بندی، این پارامتر را ارسال نکنید",
                    ),
                ],
            ),
            OpenApiParameter(
                name="ordering",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="مرتب‌سازی نتایج",
                examples=[
                    OpenApiExample(
                        "مرتب‌سازی بر اساس زمان ایجاد (نزولی)",
                        value="-created_at",
                    ),
                    OpenApiExample(
                        "مرتب‌سازی بر اساس اولویت",
                        value="priority",
                    ),
                ],
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="لیست تیکت‌ها با موفقیت دریافت شد",
                examples=[
                    OpenApiExample(
                        "مثال پاسخ موفق",
                        value=[
                            {
                                "id": 1,
                                "title": "مشکل در ورود به حساب",
                                "description": "نمی‌توانم وارد حساب کاربری خود شوم",
                                "status": "open",
                                "priority": "high",
                                "category": {
                                    "id": 1,
                                    "name": "پشتیبانی فنی",
                                },
                                "created_at": "2024-01-15T10:30:00Z",
                                "updated_at": "2024-01-15T10:30:00Z",
                            }
                        ],
                    )
                ],
            ),
        },
    ),
    create=extend_schema(
        summary="ایجاد تیکت جدید",
        description="ایجاد یک تیکت جدید برای کاربر جاری با رعایت محدودیت 15 تیکت باز",
        tags=["Tickets"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "عنوان تیکت"},
                    "description": {"type": "string", "description": "توضیحات تیکت"},
                    "priority": {
                        "type": "string",
                        "enum": [priority.value for priority in TicketPriority],
                        "description": "اولویت تیکت",
                    },
                    "category_id": {"type": "integer", "description": "شناسه دسته‌بندی"},
                },
                "required": ["title", "description"],
            }
        },
        responses={
            201: OpenApiResponse(
                description="تیکت با موفقیت ایجاد شد",
                examples=[
                    OpenApiExample(
                        "مثال پاسخ موفق",
                        value={
                            "id": 1,
                            "title": "مشکل در ورود به حساب",
                            "description": "رمز عبور را فراموش کرده‌ام و نمی‌توانم وارد حساب شوم",
                            "priority": "normal",
                            "category_id": 2,
                            "status": "open",
                            "created_at": "2024-01-15T10:30:00Z",
                            "updated_at": "2024-01-15T10:30:00Z",
                        },
                    )
                ],
            ),
            400: OpenApiResponse(description="خطا در داده‌های ورودی"),
            429: OpenApiResponse(description="بیش از حد مجاز تیکت باز دارید"),
        },
    ),
    retrieve=extend_schema(
        summary="مشاهده جزئیات تیکت",
        description="دریافت جزئیات یک تیکت خاص با پیام‌های مرتبط به صورت صفحه‌بندی شده",
        tags=["Tickets"],
        responses={
            200: OpenApiResponse(
                description="اطلاعات تیکت با موفقیت دریافت شد",
                examples=[
                    OpenApiExample(
                        "مثال پاسخ موفق",
                        value={
                            "ticket": {
                                "id": 1,
                                "title": "مشکل در ورود به حساب",
                                "description": "نمی‌توانم وارد حساب کاربری خود شوم",
                                "status": "open",
                                "priority": "high",
                                "category": {
                                    "id": 1,
                                    "name": "پشتیبانی فنی",
                                },
                                "created_at": "2024-01-15T10:30:00Z",
                            },
                            "messages": {
                                "results": [
                                    {
                                        "id": 1,
                                        "content": "لطفاً رمز عبور خود را بازنشانی کنید",
                                        "sender": "staff",
                                        "created_at": "2024-01-15T10:35:00Z",
                                        "attachments": [],
                                    }
                                ],
                                "pagination": {
                                    "count": 1,
                                    "page": 1,
                                    "pages": 1,
                                    "per_page": 10,
                                },
                            },
                        },
                    )
                ],
            ),
            404: OpenApiResponse(description="تیکت یافت نشد"),
        },
    ),
)


# Add Message Action Schema
add_message_schema = extend_schema(
    summary="افزودن پیام به تیکت",
    description="افزودن یک پیام جدید به تیکت موجود با امکان ارسال فایل ضمیمه",
    tags=["Tickets"],
    request={
        "multipart/form-data": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "متن پیام",
                },
                "reply_to": {
                    "type": "integer",
                    "description": "شناسه پیام پاسخ داده شده",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string", "format": "binary"},
                    "description": "فایل‌های پیوست (حداکثر 2 فایل)",
                },
            },
            "required": ["content"],
        }
    },
    responses={
        201: OpenApiResponse(
            description="پیام با موفقیت افزوده شد",
            examples=[
                OpenApiExample(
                    "مثال پاسخ موفق",
                    value={
                        "id": 2,
                        "content": "مشکل همچنان پابرجاست",
                        "sender": "user",
                        "created_at": "2024-01-15T11:00:00Z",
                        "attachments": [
                            {
                                "id": 1,
                                "filename": "screenshot.png",
                                "size": 102400,
                                "url": "/media/tickets/attachments/screenshot.png",
                            }
                        ],
                    },
                )
            ],
        ),
        400: OpenApiResponse(
            description="خطا در داده‌های ورودی",
            examples=[
                OpenApiExample(
                    "فایل بیش از حد مجاز",
                    value={"files": ["حداکثر 2 فایل مجاز است"]},
                ),
                OpenApiExample(
                    "فایل بیش از حجم مجاز",
                    value={"files": ["حداکثر حجم فایل 5MB است"]},
                ),
                OpenApiExample(
                    "نوع فایل نامعتبر",
                    value={"files": ["نوع فایل مجاز نیست"]},
                ),
            ],
        ),
        404: OpenApiResponse(description="تیکت یافت نشد"),
    },
)


# Error Response Schema
error_response_schema = extend_schema(
    summary="خطای اعتبارسنجی",
    description="در صورت بروز خطا در داده‌های ورودی",
    responses={
        400: OpenApiResponse(
            description="خطا در داده‌های ورودی",
            examples=[
                OpenApiExample(
                    "خطای اعتبارسنجی",
                    value={
                        "field_name": ["این فیلد الزامی است"],
                    },
                )
            ],
        ),
    },
)
