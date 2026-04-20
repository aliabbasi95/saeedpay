# wallets/api/internal/v1/schema/wallet.py

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

from wallets.api.internal.v1.serializers import (
    NationalIdInputSerializer,
    WalletSerializer,
)

internal_customer_wallets_by_national_id_schema = extend_schema(
    tags=["Wallet · Internal"],
    summary="دریافت کیف پول‌های مشتری با کد ملی",
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
            value={"national_id": "1234567890"},
            request_only=True,
        ),
        OpenApiExample(
            "Response",
            value=[
                {
                    "kind_display": "نقدی",
                    "balance": 1200000,
                }
            ],
            response_only=True,
        ),
    ],
)
