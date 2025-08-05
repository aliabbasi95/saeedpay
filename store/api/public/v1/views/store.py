# store/api/public/v1/views/store.py

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.mixins import (
    CreateModelMixin, ListModelMixin,
    RetrieveModelMixin, UpdateModelMixin,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from merchants.permissions import IsMerchant
from store.api.public.v1.serializers import (
    StoreSerializer,
    StoreCreateSerializer,
)
from store.models import Store


@extend_schema(
    tags=["Store · Management"],
    summary="مدیریت فروشگاه‌ها توسط فروشنده",
    description="ایجاد، مشاهده، و ویرایش فروشگاه‌های متعلق به فروشنده جاری"
)
class StoreViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet
):
    permission_classes = [IsAuthenticated, IsMerchant]

    def get_queryset(self):
        return Store.objects.filter(merchant=self.request.user.merchant)

    def get_serializer_class(self):
        if self.action == "create":
            return StoreCreateSerializer
        return StoreSerializer

    def perform_create(self, serializer):
        serializer.save(merchant=self.request.user.merchant)

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.get_status_number() > 1:
            raise PermissionDenied(
                "ویرایش فروشگاه پس از تأیید امکان‌پذیر نیست."
            )
        serializer.save()
