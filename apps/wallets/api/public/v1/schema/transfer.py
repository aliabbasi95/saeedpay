# wallets/api/public/v1/schema/transfer.py

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
)

from wallets.api.public.v1.serializers.transfer import (
    WalletTransferConfirmSerializer,
    WalletTransferCreateSerializer,
    WalletTransferDetailSerializer,
)

WALLET_TRANSFERS_TAG = "Wallet · Transfers"

transfers_list_schema = extend_schema(
    tags=[WALLET_TRANSFERS_TAG],
    summary="List wallet transfer requests",
    description=(
        "List transfer requests in which the authenticated user is involved "
        "as sender, receiver, or phone-based intended receiver."
    ),
    parameters=[
        OpenApiParameter(
            name="role",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Filter role: `all`, `sender`, or `receiver`.",
        ),
        OpenApiParameter(
            name="status",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Transfer status filter.",
        ),
        OpenApiParameter(
            name="ordering",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Ordering: `-created_at` or `created_at`.",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=WalletTransferDetailSerializer(many=True),
            description="Transfer list returned successfully.",
        ),
    },
)

transfer_retrieve_schema = extend_schema(
    tags=[WALLET_TRANSFERS_TAG],
    summary="Retrieve a transfer request",
    description="Return details of a transfer request accessible to the current user.",
    responses={
        200: OpenApiResponse(
            response=WalletTransferDetailSerializer,
            description="Transfer retrieved successfully.",
        ),
        404: OpenApiResponse(description="Transfer not found."),
    },
)

transfer_create_schema = extend_schema(
    tags=[WALLET_TRANSFERS_TAG],
    summary="Create a transfer request",
    description=(
        "Create a wallet transfer request from one of the authenticated user's wallets "
        "to another user's wallet or phone number."
    ),
    request=WalletTransferCreateSerializer,
    responses={
        201: OpenApiResponse(
            response=WalletTransferDetailSerializer,
            description="Transfer request created successfully.",
        ),
        400: OpenApiResponse(description="Validation or business rule error."),
    },
    examples=[
        OpenApiExample(
            "CreateTransferRequest",
            request_only=True,
            value={
                "sender_wallet_id": 10,
                "amount": 250000,
                "receiver_phone_number": "09120001122",
                "description": "Split bill",
            },
        )
    ],
)

transfer_confirm_schema = extend_schema(
    tags=[WALLET_TRANSFERS_TAG],
    summary="Confirm an incoming transfer",
    description=(
        "Confirm a pending transfer request. "
        "For phone-based transfers, the receiver must provide a destination wallet."
    ),
    request=WalletTransferConfirmSerializer,
    responses={
        200: OpenApiResponse(
            response=WalletTransferDetailSerializer,
            description="Transfer confirmed successfully.",
        ),
        400: OpenApiResponse(description="Validation or business rule error."),
        403: OpenApiResponse(
            description="You are not allowed to confirm this transfer."
        ),
        404: OpenApiResponse(description="Transfer not found."),
    },
)

transfer_reject_schema = extend_schema(
    tags=[WALLET_TRANSFERS_TAG],
    summary="Reject an incoming transfer",
    description="Reject a pending transfer request.",
    responses={
        200: OpenApiResponse(
            response=WalletTransferDetailSerializer,
            description="Transfer rejected successfully.",
        ),
        400: OpenApiResponse(description="Transfer is not rejectable."),
        403: OpenApiResponse(
            description="You are not allowed to reject this transfer."
        ),
        404: OpenApiResponse(description="Transfer not found."),
    },
)
