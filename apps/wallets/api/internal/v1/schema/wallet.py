# apps/wallets/api/internal/v1/schema/wallet.py

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

from apps.wallets.api.internal.v1.serializers import (
    NationalIdInputSerializer,
    WalletSerializer,
)

WALLET_INTERNAL_TAG = "Wallet · Internal"

internal_customer_wallets_by_national_id_schema = extend_schema(
    tags=[WALLET_INTERNAL_TAG],
    summary="Retrieve customer wallets by national ID",
    description="Return customer wallets using a national ID lookup.",
    request=NationalIdInputSerializer,
    responses={
        200: OpenApiResponse(
            response=WalletSerializer(many=True),
            description="Wallets returned successfully.",
        ),
        404: OpenApiResponse(description="Customer not found."),
    },
    examples=[
        OpenApiExample(
            "Request",
            request_only=True,
            value={"national_id": "1234567890"},
        ),
        OpenApiExample(
            "Response",
            response_only=True,
            value=[
                {
                    "kind_display": "نقدی",
                    "balance": 1200000,
                }
            ],
        ),
    ],
)
