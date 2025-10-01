# banking/api/public/v1/schema_bank_card.py

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiExample,
)

from banking.api.public.v1.serializers import (
    BankCardSerializer,
    BankCardCreateSerializer,
    BankCardUpdateSerializer,
)

bank_card_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=["Bank Cards"],
        summary="List user's bank cards",
        description=(
            "List active bank cards of the authenticated user (soft-deleted excluded). "
            "Ordered by default first, then most recent."
        ),
        responses={200: BankCardSerializer(many=True)},
        examples=[
            OpenApiExample(
                "List",
                value=[{
                    "id": "1c2e8c3d-7e9f-4b2a-bb50-86d1b40c1abc",
                    "bank": 12, "last4": "1234",
                    "card_holder_name": "Ali Ahmadi",
                    "is_default": True, "status": "verified",
                    "is_active": True,
                    "sheba": "IR680170000000000000000000",
                    "created_at": "2025-01-10T12:00:00Z",
                    "last_used": "2025-01-15T08:00:00Z",
                    "rejection_reason": None
                }]
            )
        ],
    ),
    create=extend_schema(
        tags=["Bank Cards"],
        summary="Add a new bank card",
        request=BankCardCreateSerializer,
        responses={
            201: BankCardSerializer,
            400: OpenApiResponse(
                description="Validation error",
                examples=[OpenApiExample(
                    "InvalidCardNumber", value={
                        "card_number": ["شماره کارت نامعتبر است."]
                    }
                )],
            ),
        },
        examples=[
            OpenApiExample(
                "CreatePayload",
                request_only=True,
                value={"card_number": "6037991234567890"},
            ),
            OpenApiExample(
                "Created",
                response_only=True,
                value={
                    "id": "c47a1a9d-9a7b-4f2a-8c69-1a2b3c4d5e6f",
                    "bank": 12, "last4": "7890", "card_holder_name": "",
                    "is_default": False, "status": "pending",
                    "is_active": True, "sheba": None,
                    "created_at": "2025-01-10T12:00:00Z",
                    "last_used": None, "rejection_reason": None
                },
            ),
        ],
    ),
    retrieve=extend_schema(
        tags=["Bank Cards"],
        summary="Get bank card details",
        parameters=[OpenApiParameter(
            name="id", location=OpenApiParameter.PATH, type=str,
            description="Bank card UUID"
        )],
        responses={
            200: BankCardSerializer,
            404: OpenApiResponse(
                description="Bank card not found",
                examples=[OpenApiExample(
                    "NotFound", value={"detail": "Not found."}
                )],
            ),
        },
    ),
    update=extend_schema(
        tags=["Bank Cards"],
        summary="Update bank card",
        request=BankCardUpdateSerializer,
        parameters=[OpenApiParameter(
            name="id", location=OpenApiParameter.PATH, type=str,
            description="Bank card UUID"
        )],
        responses={
            200: BankCardSerializer,
            400: OpenApiResponse(
                description="Only rejected cards can be updated.",
                examples=[OpenApiExample(
                    "NotAllowed", value={
                        "non_field_errors": [
                            "تنها کارت‌های رد شده قابل ویرایش هستند."]
                    }
                )],
            ),
            404: OpenApiResponse(description="Not found."),
        },
        examples=[OpenApiExample(
            "UpdatePayload", request_only=True, value={
                "card_number": "6219861234567890"
            }
        )],
    ),
    partial_update=extend_schema(
        tags=["Bank Cards"],
        summary="Partially update bank card",
        request=BankCardUpdateSerializer,
        parameters=[OpenApiParameter(
            name="id", location=OpenApiParameter.PATH, type=str,
            description="Bank card UUID"
        )],
        responses={
            200: BankCardSerializer,
            400: OpenApiResponse(
                description="Only rejected cards can be updated.",
                examples=[OpenApiExample(
                    "NotAllowed", value={
                        "non_field_errors": [
                            "تنها کارت‌های رد شده قابل ویرایش هستند."]
                    }
                )],
            ),
            404: OpenApiResponse(description="Not found."),
        },
    ),
    destroy=extend_schema(
        tags=["Bank Cards"],
        summary="Delete bank card",
        parameters=[OpenApiParameter(
            name="id", location=OpenApiParameter.PATH, type=str,
            description="Bank card UUID"
        )],
        responses={
            204: OpenApiResponse(description="Bank card deleted"),
            400: OpenApiResponse(
                description="Card under review cannot be deleted.",
                examples=[OpenApiExample(
                    "Pending", value={
                        "detail": "کارت‌های در حال بررسی قابل حذف نیستند."
                    }
                )],
            ),
            404: OpenApiResponse(description="Not found."),
        },
    ),
)

set_default_action_schema = extend_schema(
    tags=["Bank Cards"],
    summary="Set bank card as default",
    description=(
        "Set a verified card as default for current user. "
        "Automatically unsets previous default."
    ),
    parameters=[OpenApiParameter(
        name="id", location=OpenApiParameter.PATH, type=str,
        description="Bank card UUID"
    )],
    request=None,
    responses={
        200: BankCardSerializer,
        403: OpenApiResponse(
            description="Only verified cards can be set as default.",
            examples=[OpenApiExample(
                "NotVerified", value={
                    "detail": "تنها کارت‌های تایید شده می‌توانند به عنوان پیش‌فرض انتخاب شوند."
                }
            )],
        ),
        404: OpenApiResponse(description="Not found."),
    },
)
