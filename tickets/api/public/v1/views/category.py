# tickets/api/public/v1/views/category.py

from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from tickets.api.public.v1.schema import ticket_category_viewset_schema
from tickets.api.public.v1.serializers.category import (
    TicketCategoryDetailSerializer,
    TicketCategoryListSerializer,
)
from tickets.models import TicketCategory


@ticket_category_viewset_schema
class TicketCategoryViewSet(
    ScopedThrottleByActionMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = TicketCategory.objects.all().order_by("id")
    permission_classes = [AllowAny]
    pagination_class = None

    throttle_scope_map = {
        "default": "ticket-categories-read",
        "list": "ticket-categories-read",
        "retrieve": "ticket-categories-read",
    }

    def get_serializer_class(self):
        if self.action == "list":
            return TicketCategoryListSerializer
        return TicketCategoryDetailSerializer
