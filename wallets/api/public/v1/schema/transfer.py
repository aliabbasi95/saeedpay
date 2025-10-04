# wallets/api/public/v1/schema/transfer.py

from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiTypes,
    OpenApiResponse,
    OpenApiExample,
)

from wallets.api.public.v1.serializers.transfer import (
    WalletTransferCreateSerializer,
    WalletTransferDetailSerializer,
    WalletTransferConfirmSerializer,
)

transfers_list_schema = extend_schema(
    tags=["Wallet · Transfers"],
    summary="List/filter wallet transfer requests",
    parameters=[
        OpenApiParameter(
            "role", OpenApiParameter.QUERY, OpenApiTypes.STR,
            description="sender|receiver|all"
        ),
        OpenApiParameter(
            "status", OpenApiParameter.QUERY, OpenApiTypes.STR,
            description="pending|success|rejected"
        ),
        OpenApiParameter(
            "ordering", OpenApiParameter.QUERY, OpenApiTypes.STR,
            description="-created_at|created_at"
        ),
    ],
    responses={200: WalletTransferDetailSerializer(many=True)},
)

transfer_retrieve_schema = extend_schema(
    tags=["Wallet · Transfers"],
    summary="Retrieve a transfer request",
    responses={
        200: WalletTransferDetailSerializer,
        404: OpenApiResponse(description="Not found")
    },
)

transfer_create_schema = extend_schema(
    tags=["Wallet · Transfers"],
    summary="Create transfer request",
    request=WalletTransferCreateSerializer,
    responses={
        201: WalletTransferDetailSerializer,
        400: OpenApiResponse(description="Validation error")
    },
    examples=[OpenApiExample(
        "نمونه", value={
            "sender_wallet_id": 10, "amount": 250000,
            "receiver_phone_number": "09120001122", "description": "Split bill"
        }, request_only=True
    )],
)

transfer_confirm_schema = extend_schema(
    tags=["Wallet · Transfers"],
    summary="Confirm an incoming transfer",
    request=WalletTransferConfirmSerializer,
    responses={
        200: WalletTransferDetailSerializer,
        400: OpenApiResponse(description="Business/validation error"),
        403: OpenApiResponse(description="Forbidden"),
        404: OpenApiResponse(description="Not found"),
    },
)

transfer_reject_schema = extend_schema(
    tags=["Wallet · Transfers"],
    summary="Reject an incoming transfer",
    responses={
        200: WalletTransferDetailSerializer,
        400: OpenApiResponse(description="Not rejectable"),
        403: OpenApiResponse(description="Forbidden"),
        404: OpenApiResponse(description="Not found"),
    },
)
