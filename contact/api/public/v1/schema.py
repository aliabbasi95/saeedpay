# contact/api/public/v1/schema.py

from drf_spectacular.utils import (
    extend_schema, OpenApiExample,
    OpenApiResponse,
)
from rest_framework import status

from contact.api.public.v1.serializers.contact import ContactCreateSerializer

contact_create_schema = extend_schema(
    summary="ارسال فرم تماس",
    description="این API برای ارسال پیام تماس توسط کاربر استفاده می‌شود. فقط از طریق Postman و Swagger قابل استفاده است.",
    request=ContactCreateSerializer,
    responses={
        status.HTTP_201_CREATED: OpenApiResponse(
            response=ContactCreateSerializer,
            description="Contact created successfully."
        ),
        status.HTTP_400_BAD_REQUEST: OpenApiResponse(
            description="BAD REQUEST (validation error or blocked client)"
        ),
    },
    examples=[
        OpenApiExample(
            'نمونه درخواست',
            value={
                'name': 'علی رضایی',
                'email': 'ali@example.com',
                'phone': '09123456789',
                'message': 'سلام، مایلم با شما همکاری کنم.'
            },
            request_only=True
        ),
        OpenApiExample(
            'نمونه پاسخ موفق',
            value={
                'name': 'علی رضایی',
                'email': 'ali@example.com',
                'phone': '09123456789',
                'message': 'سلام، مایلم با شما همکاری کنم.'
            },
            response_only=True,
            status_codes=[str(status.HTTP_201_CREATED)]
        ),
        OpenApiExample(
            'نمونه خطا',
            value={
                'detail': 'BAD REQUEST'
            },
            response_only=True,
            status_codes=[str(status.HTTP_400_BAD_REQUEST)]
        ),
    ]
)
