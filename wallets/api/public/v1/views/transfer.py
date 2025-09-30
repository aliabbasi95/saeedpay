# wallets/api/public/v1/views/transfer.py
# ViewSet for Wallet Transfers: list, create, retrieve, confirm, reject.

from django.db import models
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    extend_schema, OpenApiParameter,
    OpenApiTypes, OpenApiResponse,
)
from rest_framework import status, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from wallets.api.public.v1.serializers.transfer import (
    WalletTransferCreateSerializer,
    WalletTransferDetailSerializer,
    WalletTransferConfirmSerializer,
)
from wallets.models import WalletTransferRequest
from wallets.services import (
    create_wallet_transfer_request,
    confirm_wallet_transfer_request,
    reject_wallet_transfer_request,
)
from wallets.services.transfer import check_and_expire_transfer_request
from wallets.utils.choices import TransferStatus


@extend_schema(
    tags=["Wallet · Transfers"],
    description="User-to-user wallet transfer requests: list with filters, create, confirm/reject incoming requests."
)
class WalletTransferViewSet(
    ScopedThrottleByActionMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    """
    Transfers the current user is involved in (sender/receiver/phone).
    """
    queryset = (
        WalletTransferRequest.objects
        .select_related(
            "sender_wallet", "sender_wallet__user",
            "receiver_wallet", "receiver_wallet__user",
            "transaction",
        )
        .only(
            "id", "amount", "description", "status",
            "expires_at", "created_at", "reference_code",
            "sender_wallet_id", "receiver_wallet_id",
            "receiver_phone_number",
            "sender_wallet__id", "sender_wallet__wallet_number",
            "sender_wallet__user_id",
            "receiver_wallet__id", "receiver_wallet__wallet_number",
            "receiver_wallet__user_id",
            "transaction_id",
        )
    )
    serializer_class = WalletTransferDetailSerializer
    lookup_field = "pk"
    throttle_scope_map = {
        "default": "wallet-transfers-read",
        "list": "wallet-transfers-read",
        "retrieve": "wallet-transfers-read",
        "create": "wallet-transfers-write",
        "confirm": "wallet-transfers-write",
        "reject": "wallet-transfers-write",
    }

    @extend_schema(
        summary="List/filter wallet transfer requests",
        parameters=[
            OpenApiParameter(
                "role", OpenApiParameter.QUERY, OpenApiTypes.STR,
                description="sender | receiver | all (default: all)"
            ),
            OpenApiParameter(
                "status", OpenApiParameter.QUERY, OpenApiTypes.STR,
                description=f"e.g. {TransferStatus.PENDING_CONFIRMATION}, {TransferStatus.SUCCESS}, {TransferStatus.REJECTED}"
            ),
            OpenApiParameter(
                "ordering", OpenApiParameter.QUERY, OpenApiTypes.STR,
                description="-created_at | created_at (default: -created_at)"
            ),
        ],
        responses={200: WalletTransferDetailSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        user = request.user
        phone = getattr(getattr(user, "profile", None), "phone_number", None)
        role = request.query_params.get("role", "all")
        status_param = request.query_params.get("status")
        ordering = request.query_params.get("ordering") or "-created_at"

        if role == "sender":
            qs = self.queryset.filter(sender_wallet__user=user)
        elif role == "receiver":
            qs = self.queryset.filter(
                models.Q(receiver_wallet__user=user) |
                models.Q(receiver_phone_number=phone)
            )
        else:
            qs = self.queryset.filter(
                models.Q(sender_wallet__user=user) |
                models.Q(receiver_wallet__user=user) |
                models.Q(receiver_phone_number=phone)
            ).distinct()

        if status_param:
            qs = qs.filter(status=status_param)

        if ordering not in {"-created_at", "created_at"}:
            ordering = "-created_at"
        qs = qs.order_by(ordering)

        page = self.paginate_queryset(qs)
        if page is not None:
            ser = WalletTransferDetailSerializer(page, many=True)
            return self.get_paginated_response(ser.data)

        ser = WalletTransferDetailSerializer(qs, many=True)
        return Response(ser.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Retrieve a transfer request",
        responses={
            200: WalletTransferDetailSerializer, 404: OpenApiResponse(
                description="Transfer not found or not accessible."
            )
        },
    )
    def retrieve(self, request, *args, **kwargs):
        transfer = self._get_accessible_transfer_or_404(
            request, kwargs.get("pk")
        )
        ser = WalletTransferDetailSerializer(transfer)
        return Response(ser.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Create a wallet transfer request",
        request=WalletTransferCreateSerializer,
        responses={201: WalletTransferDetailSerializer},
    )
    def create(self, request, *args, **kwargs):
        ser = WalletTransferCreateSerializer(
            data=request.data, context={"request": request}
        )
        ser.is_valid(raise_exception=True)
        req = create_wallet_transfer_request(
            sender_wallet=ser.validated_data["sender_wallet"],
            amount=ser.validated_data["amount"],
            receiver_wallet=ser.validated_data.get("receiver_wallet"),
            receiver_phone=ser.validated_data.get("receiver_phone_number"),
            description=ser.validated_data.get("description", ""),
            creator=request.user,
        )
        out = WalletTransferDetailSerializer(req).data
        return Response(out, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Confirm an incoming transfer",
        description="Confirm a pending transfer addressed to the authenticated user.",
        request=WalletTransferConfirmSerializer,
        responses={
            200: WalletTransferDetailSerializer,
            400: OpenApiResponse(
                description="Validation error or business rule violation."
            ),
            403: OpenApiResponse(
                description="Not allowed to confirm this transfer."
            ),
            404: OpenApiResponse(description="Transfer not found."),
        },
    )
    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, *args, **kwargs):
        transfer = self._get_accessible_transfer_or_404(
            request, kwargs.get("pk")
        )
        check_and_expire_transfer_request(transfer)
        if transfer.status != TransferStatus.PENDING_CONFIRMATION:
            return Response(
                {"detail": "Transfer is not confirmable."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if transfer.receiver_phone_number and not transfer.receiver_wallet_id:
            ser = WalletTransferConfirmSerializer(
                data=request.data, context={"request": request}
            )
            ser.is_valid(raise_exception=True)
            try:
                transfer = confirm_wallet_transfer_request(
                    transfer, ser.validated_data["receiver_wallet"],
                    request.user
                )
            except Exception as e:
                return Response(
                    {"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                WalletTransferDetailSerializer(transfer).data,
                status=status.HTTP_200_OK
            )

        if transfer.receiver_wallet and transfer.receiver_wallet.user_id == request.user.id:
            try:
                transfer = confirm_wallet_transfer_request(
                    transfer, transfer.receiver_wallet, request.user
                )
            except Exception as e:
                return Response(
                    {"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                WalletTransferDetailSerializer(transfer).data,
                status=status.HTTP_200_OK
            )

        return Response(
            {"detail": "You are not allowed to confirm this transfer."},
            status=status.HTTP_403_FORBIDDEN
        )

    @extend_schema(
        summary="Reject an incoming transfer",
        responses={
            200: WalletTransferDetailSerializer,
            400: OpenApiResponse(description="Transfer is not rejectable."),
            403: OpenApiResponse(
                description="Not allowed to reject this transfer."
            ),
            404: OpenApiResponse(description="Transfer not found."),
        },
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, *args, **kwargs):
        transfer = self._get_accessible_transfer_or_404(
            request, kwargs.get("pk")
        )
        if transfer.status != TransferStatus.PENDING_CONFIRMATION:
            return Response(
                {"detail": "Transfer is not rejectable."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            transfer = reject_wallet_transfer_request(transfer)
        except Exception as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            WalletTransferDetailSerializer(transfer).data,
            status=status.HTTP_200_OK
        )

    # -- helpers --

    def _get_accessible_transfer_or_404(
            self, request, pk: int
    ) -> WalletTransferRequest:
        """User must be a party (sender/receiver) or intended phone receiver."""
        user = request.user
        phone = getattr(getattr(user, "profile", None), "phone_number", None)
        return get_object_or_404(
            self.queryset,
            models.Q(id=pk),
            models.Q(sender_wallet__user=user) |
            models.Q(receiver_wallet__user=user) |
            models.Q(receiver_phone_number=phone),
        )
