# apps/wallets/api/public/v1/schema/wallet.py

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
)

from apps.wallets.api.public.v1.serializers import WalletSerializer

WALLET_WALLETS_TAG = "Wallet · Wallets"

wallets_list_schema = extend_schema(
    tags=[WALLET_WALLETS_TAG],
    summary="List user's wallets",
    description=("Return wallets of the authenticated user filtered by `owner_type`."),
    parameters=[
        OpenApiParameter(
            name="owner_type",
            location=OpenApiParameter.QUERY,
            required=True,
            type=OpenApiTypes.STR,
            description="Wallet owner type. Example: `customer` or `merchant`.",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=WalletSerializer(many=True),
            description="Wallet list returned successfully.",
        ),
        400: OpenApiResponse(description="Invalid query parameters."),
        401: OpenApiResponse(description="Authentication required."),
    },
    examples=[
        OpenApiExample(
            "WalletListResponse",
            response_only=True,
            value=[
                {
                    "id": 5,
                    "wallet_number": "601234567890",
                    "kind": "cash",
                    "kind_display": "نقدی",
                    "owner_type": "customer",
                    "owner_type_display": "مشتری",
                    "spendable_amount": 1200000,
                    "created_at": "2025-01-01T10:00:00Z",
                    "updated_at": "2025-01-05T10:00:00Z",
                }
            ],
        )
    ],
)
