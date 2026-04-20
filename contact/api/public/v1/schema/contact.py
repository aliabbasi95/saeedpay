# contact/api/public/v1/schema/contact.py

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status

from contact.api.public.v1.serializers.contact import ContactCreateSerializer

contact_create_schema = extend_schema(
    tags=["Contact"],
    summary="ارسال فرم تماس",
    description="ثبت پیام تماس عمومی توسط کاربر.",
    request=ContactCreateSerializer,
    responses={
        status.HTTP_201_CREATED: OpenApiResponse(
            response=ContactCreateSerializer,
            description="پیام تماس با موفقیت ثبت شد.",
        ),
        status.HTTP_400_BAD_REQUEST: OpenApiResponse(
            description="خطای اعتبارسنجی یا محدودیت درخواست.",
        ),
    },
    examples=[
        OpenApiExample(
            "نمونه درخواست",
            value={
                "name": "علی رضایی",
                "email": "ali@example.com",
                "phone": "09123456789",
                "message": "سلام، مایلم با شما همکاری کنم.",
            },
            request_only=True,
        ),
        OpenApiExample(
            "نمونه پاسخ موفق",
            value={
                "name": "علی رضایی",
                "email": "ali@example.com",
                "phone": "09123456789",
                "message": "سلام، مایلم با شما همکاری کنم.",
            },
            response_only=True,
            status_codes=[str(status.HTTP_201_CREATED)],
        ),
        OpenApiExample(
            "نمونه خطا",
            value={"detail": "BAD REQUEST"},
            response_only=True,
            status_codes=[str(status.HTTP_400_BAD_REQUEST)],
        ),
    ],
)
