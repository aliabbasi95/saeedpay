# tickets/api/public/v1/views/category.py

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from tickets.api.public.v1.serializers import (
    TicketCategoryListSerializer,
    TicketCategoryDetailSerializer,
)
from tickets.models import TicketCategory


@extend_schema_view(
    list=extend_schema(
        tags=["Tickets"],
        summary="لیست دسته‌بندی‌های تیکت",
        description="دریافت لیست تمام دسته‌بندی‌های تیکت با فیلد‌های محدود",
    ),
    retrieve=extend_schema(
        tags=["Tickets"],
        summary="جزئیات دسته‌بندی تیکت",
        description="دریافت اطلاعات کامل یک دسته‌بندی تیکت",
    ),
)
class TicketCategoryViewSet(
    ScopedThrottleByActionMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
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
