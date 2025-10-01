# banking/api/public/v1/views/bank_card.py

import logging

from django.utils.translation import gettext_lazy as _
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from banking.api.public.v1.schema import bank_card_viewset_schema
from banking.api.public.v1.schema.schema_bank_card import \
    set_default_action_schema
from banking.api.public.v1.serializers import (
    BankCardSerializer,
    BankCardCreateSerializer,
    BankCardUpdateSerializer,
)
from banking.models import BankCard
from banking.services import bank_card_service
from banking.utils.choices import BankCardStatus
from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin

logger = logging.getLogger(__name__)


@bank_card_viewset_schema
class BankCardViewSet(ScopedThrottleByActionMixin, viewsets.ModelViewSet):
    """
    User-owned bank cards (soft-delete). Write ops are throttled separately.
    """
    lookup_field = "id"
    pagination_class = None
    throttle_scope_map = {
        "default": "bank-cards-read",
        "create": "bank-cards-write",
        "update": "bank-cards-write",
        "partial_update": "bank-cards-write",
        "destroy": "bank-cards-write",
        "set_default": "bank-cards-write",
    }

    def get_queryset(self):
        # Only user's active cards; join bank for fewer queries in lists
        return (
            BankCard.objects
            .filter(user=self.request.user, is_active=True)
            .select_related("bank")
            .order_by("-is_default", "-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return BankCardCreateSerializer
        if self.action in ["update", "partial_update"]:
            return BankCardUpdateSerializer
        return BankCardSerializer

    def create(self, request, *args, **kwargs):
        """
        Create a new card in PENDING, then enqueue async validation.
        Response uses output serializer to avoid exposing write-only fields.
        """
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        output = BankCardSerializer(serializer.instance)
        headers = self.get_success_headers(output.data)
        return Response(
            output.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def perform_create(self, serializer):
        instance = serializer.save()
        # old_status=None on create
        bank_card_service.enqueue_validation_if_pending(None, instance)

    def perform_update(self, serializer):
        """
        Only REJECTED cards can be edited; serializer enforces this.
        After update, status becomes PENDING and re-validation is enqueued.
        """
        old_status = serializer.instance.status
        instance = serializer.save()
        bank_card_service.enqueue_validation_if_pending(old_status, instance)

    def perform_destroy(self, instance):
        """
        Soft-delete; PENDING cards cannot be deleted.
        """
        if instance.status == BankCardStatus.PENDING:
            raise ValidationError(_("کارت‌های در حال بررسی قابل حذف نیستند."))
        bank_card_service.soft_delete_card(instance)

    @set_default_action_schema
    @action(
        detail=True,
        methods=["patch"],
        url_path="set-default",
        url_name="set-default"
    )
    def set_default(self, request, id=None):
        """
        Set this verified card as user's default.
        """
        card = self.get_object()  # already filtered by user + is_active
        if card.status != BankCardStatus.VERIFIED:
            return Response(
                {
                    "detail": _(
                        "تنها کارت‌های تایید شده می‌توانند به عنوان پیش‌فرض انتخاب شوند."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        updated = bank_card_service.set_as_default(request.user, id)
        return Response(BankCardSerializer(updated).data)
