# contact/api/public/v1/schema/contact.py

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status

from contact.api.public.v1.serializers.contact import ContactCreateSerializer

CONTACT_TAG = "Public · Contact"

contact_create_schema = extend_schema(
    tags=[CONTACT_TAG],
    summary="Submit contact form",
    description="Submit a public contact message.",
    request=ContactCreateSerializer,
    responses={
        status.HTTP_201_CREATED: OpenApiResponse(
            response=ContactCreateSerializer,
            description="Contact message created successfully.",
        ),
        status.HTTP_400_BAD_REQUEST: OpenApiResponse(
            description="Validation error or throttling limitation.",
        ),
    },
    examples=[
        OpenApiExample(
            "Request",
            value={
                "name": "علی رضایی",
                "email": "ali@example.com",
                "phone": "09123456789",
                "message": "سلام، مایلم با شما همکاری کنم.",
            },
            request_only=True,
        ),
        OpenApiExample(
            "SuccessResponse",
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
            "ErrorResponse",
            value={"detail": "BAD REQUEST"},
            response_only=True,
            status_codes=[str(status.HTTP_400_BAD_REQUEST)],
        ),
    ],
)
