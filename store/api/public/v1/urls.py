# store/api/public/v1/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from store.api.public.v1.views import (
    StoreApiKeyRegenerateView,
    StoreViewSet,
    PublicStoreViewSet,
    StoreContractViewSet,
)

app_name = "store_public_v1"

router = DefaultRouter()
router.register("stores", StoreViewSet, basename="store")
router.register("public-stores", PublicStoreViewSet, basename="public-store")
router.register(
    "store-contract", StoreContractViewSet, basename="store-contract"
)

urlpatterns = [
    path(
        "regenerate-api-key/",
        StoreApiKeyRegenerateView.as_view(),
        name="regenerate-api-key"
    ),
    path("", include(router.urls)),
]
