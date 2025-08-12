# tickets/api/public/v1/views/category.py
from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, extend_schema_view

from tickets.models import TicketCategory
from tickets.api.public.v1.serializers.ticket import (
    TicketCategoryListSerializer,
    TicketCategoryDetailSerializer,
)


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
    """
    ViewSet برای مدیریت دسته‌بندی‌های تیکت
    - لیست دسته‌بندی‌ها: فقط id، name و description
    - جزئیات دسته‌بندی: تمام فیلدها
    """
    queryset = TicketCategory.objects.all()
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == "list":
            return TicketCategoryListSerializer
        return TicketCategoryDetailSerializer
