# banking/api/public/v1/schema_bank.py

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from banking.api.public.v1.serializers import (
    BankDetailSerializer,
    BankSerializer,
)

BANKS_TAG = "Banking · Banks"

bank_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=[BANKS_TAG],
        summary="List all banks",
        description=(
            "Retrieve a list of all available banks. "
            "Useful for displaying bank options in forms or interfaces."
        ),
        responses={
            200: BankSerializer(many=True),
        },
        examples=[
            OpenApiExample(
                "List",
                value=[
                    {
                        "id": 1,
                        "name": "Mellat",
                        "logo": "/media/banks/mellat.svg",
                        "color": "#e53935",
                    }
                ],
            )
        ],
    ),
    retrieve=extend_schema(
        tags=[BANKS_TAG],
        summary="Get bank details",
        description="Retrieve detailed information about a specific bank by its ID.",
        parameters=[
            OpenApiParameter(
                name="id",
                location=OpenApiParameter.PATH,
                type=int,
                description="Bank ID",
            )
        ],
        responses={
            200: BankDetailSerializer,
            404: OpenApiResponse(
                description="Bank not found",
                examples=[OpenApiExample("NotFound", value={"detail": "Not found."})],
            ),
        },
        examples=[
            OpenApiExample(
                "Detail",
                value={
                    "id": 1,
                    "name": "Mellat",
                    "logo": "/media/banks/mellat.svg",
                    "color": "#e53935",
                    "created_at": "2025-01-01T08:00:00Z",
                    "updated_at": "2025-01-02T09:10:00Z",
                },
            )
        ],
    ),
)
