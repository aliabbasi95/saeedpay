# banking/api/public/v1/views/bank_card.py

import logging
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiParameter,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from banking.models import BankCard
from banking.utils.choices import BankCardStatus
from banking.api.public.v1.serializers import (
    BankCardSerializer,
    BankCardCreateSerializer,
    BankCardUpdateSerializer,
)
from banking.services import bank_card_service
from banking.tasks import validate_card_task

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="List user's bank cards",
        description=(
            "Retrieve a list of all active bank cards belonging to the "
            "authenticated user. Only returns cards that are not soft-deleted "
            "(is_active=True). Cards are ordered by default status first, "
            "then by most recently added."
        ),
        tags=["Bank Cards"],
        responses={
            200: BankCardSerializer(many=True),
        },
    ),
    create=extend_schema(
        summary="Add a new bank card",
        description=(
            "Add a new bank card to the user's account. The card will be "
            "created with PENDING status and automatically scheduled for "
            "validation. Only the card number is required for creation. The "
            "card number must pass Luhn algorithm validation."
        ),
        tags=["Bank Cards"],
        request=BankCardCreateSerializer,
        responses={
            201: BankCardSerializer,
            400: {
                "description": "Validation error",
                "examples": {
                    "application/json": {
                        "card_number": ["Invalid card number."]
                    }
                },
            },
        },
    ),
    retrieve=extend_schema(
        summary="Get bank card details",
        description=(
            "Retrieve detailed information about a specific bank card. "
            "Only returns cards belonging to the authenticated user that are "
            "active."
        ),
        tags=["Bank Cards"],
        parameters=[
            OpenApiParameter(
                name='id',
                type=str,
                location=OpenApiParameter.PATH,
                description='Unique UUID identifier for the bank card'
            ),
        ],
        responses={
            200: BankCardSerializer,
            404: {
                "description": "Bank card not found or doesn't belong to user",
                "examples": {"application/json": {"detail": "Not found."}},
            },
        },
    ),
    update=extend_schema(
        summary="Update bank card",
        description=(
            "Update a bank card's information. Only rejected cards can be "
            "updated. Updating a card will change its status back to PENDING "
            "and schedule it for re-validation. "
            "Cards with PENDING status cannot be updated."
        ),
        tags=["Bank Cards"],
        parameters=[
            OpenApiParameter(
                name='id',
                type=str,
                location=OpenApiParameter.PATH,
                description='Unique UUID identifier for the bank card'
            ),
        ],
        request=BankCardUpdateSerializer,
        responses={
            200: BankCardSerializer,
            400: {
                "description": "Validation error - card cannot be updated",
                "examples": {
                    "application/json": {
                        "non_field_errors": [
                            "Only rejected cards can be updated."
                        ]
                    }
                },
            },
            404: {
                "description": "Bank card not found",
                "examples": {"application/json": {"detail": "Not found."}},
            },
        },
    ),
    partial_update=extend_schema(
        summary="Partially update bank card",
        description=(
            "Partially update a bank card's information. Only rejected cards "
            "can be updated. Updating a card will change its status back to "
            "PENDING and schedule it for re-validation. "
            "Cards with PENDING status cannot be updated."
        ),
        tags=["Bank Cards"],
        parameters=[
            OpenApiParameter(
                name='id',
                type=str,
                location=OpenApiParameter.PATH,
                description='Unique UUID identifier for the bank card'
            ),
        ],
        request=BankCardUpdateSerializer,
        responses={
            200: BankCardSerializer,
            400: {
                "description": "Validation error - card cannot be updated",
                "examples": {
                    "application/json": {
                        "non_field_errors": [
                            "Only rejected cards can be updated."
                        ]
                    }
                },
            },
            404: {
                "description": "Bank card not found",
                "examples": {"application/json": {"detail": "Not found."}},
            },
        },
    ),
    destroy=extend_schema(
        summary="Delete bank card",
        description=(
            "Soft delete a bank card by setting is_active=False. "
            "Cards with PENDING status cannot be deleted as they are still "
            "under review. This operation is irreversible through the API."
        ),
        tags=["Bank Cards"],
        parameters=[
            OpenApiParameter(
                name='id',
                type=str,
                location=OpenApiParameter.PATH,
                description='Unique UUID identifier for the bank card'
            ),
        ],
        responses={
            204: {"description": "Bank card successfully deleted"},
            400: {
                "description": "Validation error - card cannot be deleted",
                "examples": {
                    "application/json": {
                        "detail": "Cards under review cannot be deleted."
                    }
                },
            },
            404: {
                "description": "Bank card not found",
                "examples": {"application/json": {"detail": "Not found."}},
            },
        },
    ),
)
class BankCardViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user bank cards.

    This viewset provides full CRUD operations for bank cards, allowing users \
to:
    - List their active bank cards
    - Add new bank cards (with automatic validation)
    - View detailed information about their cards
    - Update rejected cards (triggers re-validation)
    - Delete cards (soft delete)
    - Set a verified card as default

    All operations are scoped to the authenticated user's cards only.
    Card validation is handled asynchronously via Celery tasks.
    """

    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        return BankCard.objects.filter(user=self.request.user, is_active=True)

    def get_serializer_class(self):
        if self.action == "create":
            return BankCardCreateSerializer
        if self.action in ["update", "partial_update"]:
            return BankCardUpdateSerializer
        return BankCardSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # Use the output serializer for the response
        output_serializer = BankCardSerializer(serializer.instance)
        headers = self.get_success_headers(serializer.data)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        """
        Create a new bank card and trigger validation if status is PENDING.
        """
        instance = serializer.save()

        # Submit validation task if card is in pending status
        if instance.status == BankCardStatus.PENDING:
            try:
                validate_card_task.delay(str(instance.id))
                logger.info(
                    f"Card validation task scheduled for card {instance.id}"
                )
            except Exception as exc:
                logger.error(
                    f"Failed to schedule validation task for card "
                    f"{instance.id}: {str(exc)}"
                )

    def perform_update(self, serializer):
        """
        Update a bank card and trigger validation if status becomes PENDING.
        """
        old_status = serializer.instance.status
        instance = serializer.save()
        instance.full_clean()

        # Submit validation task if card status became PENDING after update
        if (
            instance.status == BankCardStatus.PENDING
            and old_status != BankCardStatus.PENDING
        ):
            try:
                validate_card_task.delay(str(instance.id))
                logger.info(
                    f"Card validation task for updated card {instance.id} "
                    "scheduled."
                )
            except Exception as exc:
                logger.error(
                    f"Failed to schedule validation task for updated card "
                    f"{instance.id}: {str(exc)}"
                )

    def perform_destroy(self, instance):
        """
        Soft delete a bank card, but prevent deletion if status is PENDING.
        """
        if instance.status == BankCardStatus.PENDING:
            raise ValidationError(_("کارت‌های در حال بررسی قابل حذف نیستند."))

        bank_card_service.soft_delete_card(instance)

    @extend_schema(
        summary="Set bank card as default",
        description=(
            "Set a specific bank card as the default card for the user. "
            "Only verified cards can be set as default. This will "
            "automatically unset any previously default card for the user. "
            "Default cards are typically used for primary payment "
            "operations."
        ),
        tags=["Bank Cards"],
        parameters=[
            OpenApiParameter(
                name='id',
                type=str,
                location=OpenApiParameter.PATH,
                description='Unique UUID identifier for the bank card'
            ),
        ],
        request=None,
        responses={
            200: BankCardSerializer,
            403: {
                "description": "Card cannot be set as default",
                "examples": {
                    "application/json": {
                        "detail": "Only verified cards can be set as default."
                    }
                },
            },
            404: {
                "description": "Bank card not found",
                "examples": {"application/json": {"detail": "Not found."}},
            },
        },
    )
    @action(
        detail=True,
        methods=["patch"],
        url_path="set-default",
        url_name="set-default",
    )
    def set_default(self, request, id=None):
        card = self.get_object()
        if card.status != BankCardStatus.VERIFIED:
            return Response(
                {
                    "detail": _(
                        (
                            "تنها کارت‌های "
                            "تایید شده می‌توانند به عنوان پیش‌فرض انتخاب شوند."
                        )
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        card = bank_card_service.set_as_default(request.user, id)
        return Response(BankCardSerializer(card).data)
