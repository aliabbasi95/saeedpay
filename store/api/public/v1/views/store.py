# store/api/public/v1/views/store.py

from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import extend_schema_view
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from merchants.permissions import IsMerchant
from store.api.public.v1.schema import (
    store_list_schema,
    store_create_schema,
    store_retrieve_schema,
    store_delete_schema,
    public_store_list_schema,
    public_store_retrieve_schema,
    store_update_put_schema,
    store_partial_update_schema,
)
from store.api.public.v1.serializers import \
    StoreApiKeyRegenerateResponseSerializer
from store.api.public.v1.serializers import (
    StoreSerializer,
    StoreCreateSerializer,
    PublicStoreSerializer,
)
from store.models import Store
from store.services.apikey import regenerate_store_api_key


@extend_schema_view(
    list=store_list_schema,
    create=store_create_schema,
    retrieve=store_retrieve_schema,
    update=store_update_put_schema,
    partial_update=store_partial_update_schema,
    destroy=store_delete_schema,
)
class StoreViewSet(
    ScopedThrottleByActionMixin,
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

    throttle_scope_map = {
        "default": "stores-read",
        "create": "stores-write",
        "update": "stores-write",
        "partial_update": "stores-write",
        "destroy": "stores-write",
        "regenerate_api_key": "store-apikey-regen",
    }

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
        if instance.status > 1:
            raise PermissionDenied(
                "ویرایش فروشگاه پس از تأیید امکان‌پذیر نیست."
            )
        instance.store_reviewer_verification = 0
        serializer.save()

    @extend_schema(
        tags=["Store · API Key"],
        summary="تولید مجدد API Key فروشگاه",
        description="تنها مرچنت مالک فروشگاه می‌تواند کلید را بازتولید کند.",
        responses={201: StoreApiKeyRegenerateResponseSerializer},
    )
    @action(detail=True, methods=["post"], url_path="regenerate-api-key")
    def regenerate_api_key(self, request, pk=None):
        store = self.get_object()
        new_key = regenerate_store_api_key(store)
        payload = {"api_key": new_key}
        return Response(
            StoreApiKeyRegenerateResponseSerializer(payload).data,
            status=201
        )


@extend_schema_view(
    list=public_store_list_schema,
    retrieve=public_store_retrieve_schema,
)
class PublicStoreViewSet(
    ScopedThrottleByActionMixin,
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet
):
    permission_classes = []
    serializer_class = PublicStoreSerializer

    throttle_scope_map = {
        "default": "public-stores-read",
        "list": "public-stores-read",
        "retrieve": "public-stores-read",
    }

    def get_queryset(self):
        return Store.objects.filter(
            status=2,  # 2=finalized/approved (store_reviewer_verification=1)
            is_active=True,
        )
