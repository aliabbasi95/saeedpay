# tickets/api/public/v1/views/ticket.py

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.mixins import (
    CreateModelMixin, ListModelMixin,
    RetrieveModelMixin,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from lib.cas_auth.erp.pagination import CustomPagination
from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from tickets.api.public.v1.schema import (
    ticket_viewset_schema,
    messages_list_schema,
    add_message_schema,
)
from tickets.api.public.v1.serializers import (
    TicketSerializer,
    TicketCreateSerializer,
    TicketMessageSerializer,
    TicketMessageCreateSerializer,
)
from tickets.filters import TicketFilter
from tickets.models import Ticket, TicketMessage


@ticket_viewset_schema
class TicketViewSet(
    ScopedThrottleByActionMixin,
    CreateModelMixin, ListModelMixin, RetrieveModelMixin, GenericViewSet,
):
    """
    list:     User's tickets (filter + ordering).
    retrieve: Single ticket (only owner).
    create:   Create new ticket (first message optional via `description`).
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = TicketFilter
    ordering_fields = ["id", "created_at", "updated_at", "priority", "status"]
    ordering = ["-id"]

    throttle_scope_map = {
        "default": "tickets-read",
        "list": "tickets-read",
        "retrieve": "tickets-read",
        "create": "tickets-write",
        "messages": "tickets-read",
        "add_message": "ticket-message-add",
    }

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Ticket.objects.none()
        user = getattr(getattr(self, "request", None), "user", None)
        if not user or not user.is_authenticated:
            return Ticket.objects.none()
        return Ticket.objects.filter(user=user).select_related("category")

    def get_serializer_class(self):
        if self.action == "create":
            return TicketCreateSerializer
        return TicketSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @messages_list_schema
    @action(detail=True, methods=["get"], url_path="messages")
    def messages(self, request, pk=None):
        ticket = self.get_object()
        qs = TicketMessage.objects.filter(ticket=ticket).order_by("id")
        paginator = CustomPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = TicketMessageSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @add_message_schema
    @action(detail=True, methods=["post"], url_path="messages")
    def add_message(self, request, pk=None):
        ticket = self.get_object()
        ser = TicketMessageCreateSerializer(
            data=request.data, context={"request": request, "ticket": ticket}
        )
        ser.is_valid(raise_exception=True)
        message = ser.save()
        return Response(
            TicketMessageSerializer(message).data,
            status=status.HTTP_201_CREATED
        )
