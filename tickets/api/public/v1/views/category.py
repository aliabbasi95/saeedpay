# tickets/api/public/v1/views/category.py
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

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
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    queryset = TicketCategory.objects.all().order_by("id")
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == "list":
            return TicketCategoryListSerializer
        return TicketCategoryDetailSerializer
