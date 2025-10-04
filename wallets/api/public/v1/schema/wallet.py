# wallets/api/public/v1/schema/wallet.py

from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiTypes,
    OpenApiResponse,
    OpenApiExample,
)

from wallets.api.public.v1.serializers import WalletSerializer

wallets_list_schema = extend_schema(
    tags=["Wallet · Wallets"],
    summary="List user's wallets",
    parameters=[
        OpenApiParameter(
            "owner_type", OpenApiParameter.QUERY, OpenApiTypes.STR,
            description="customer|merchant"
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=WalletSerializer(many=True), description="OK"
        )
    },
    examples=[
        OpenApiExample(
            "نمونه", value=[{
                "id": 5, "wallet_number": "601234567890",
                "kind": "cash", "kind_display": "نقدی",
                "owner_type": "customer", "owner_type_display": "مشتری",
                "spendable_amount": 1200000,
                "created_at": "2025-01-01T10:00:00Z",
                "updated_at": "2025-01-05T10:00:00Z",
            }], response_only=True
        )
    ],
)
