# store/api/public/v1/views/store.py

from drf_spectacular.utils import extend_schema_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from merchants.permissions import IsMerchant
from store.api.public.v1.schema import (
    store_list_schema,
    store_create_schema,
    store_retrieve_schema,
    store_update_schema,
    store_delete_schema,
    public_store_list_schema,
    public_store_retrieve_schema,
)
from store.api.public.v1.serializers import (
    StoreSerializer,
    StoreCreateSerializer,
    PublicStoreSerializer,
)
from store.models import Store


@extend_schema_view(
    list=store_list_schema,
    create=store_create_schema,
    retrieve=store_retrieve_schema,
    update=store_update_schema,
    partial_update=store_update_schema,
    destroy=store_delete_schema,
)
class StoreViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    GenericViewSet,
):
    permission_classes = [IsAuthenticated, IsMerchant]
    queryset = Store.objects.none()
    serializer_class = StoreSerializer

    def get_queryset(self):
        user = getattr(getattr(self, "request", None), "user", None)
        if not user or not hasattr(user, "merchant"):
            return Store.objects.none()
        return Store.objects.filter(merchant=user.merchant)

    def get_serializer_class(self):
        if getattr(self, "action", None) == "create":
            return StoreCreateSerializer
        return StoreSerializer

    def perform_create(self, serializer):
        serializer.save(merchant=self.request.user.merchant)

    def perform_update(self, serializer):
        instance = self.get_object()
        # Check if store is already finalized (status 2) or rejected (status 3)
        if instance.status > 1:
            raise PermissionDenied(
                "ویرایش فروشگاه پس از تأیید امکان‌پذیر نیست."
            )
        # Reset verification to pending when updating
        instance.store_reviewer_verification = 0
        serializer.save()


@extend_schema_view(
    list=public_store_list_schema,
    retrieve=public_store_retrieve_schema,
)
class PublicStoreViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    permission_classes = []
    serializer_class = PublicStoreSerializer

    def get_queryset(self):
        # Only show finalized stores (status 2 = finalized/approved in cardboard system)
        return Store.objects.filter(
            status=2,  # 2=finalized/approved (store_reviewer_verification=1)
            is_active=True,
        )
