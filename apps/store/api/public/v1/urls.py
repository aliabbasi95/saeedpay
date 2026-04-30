# apps/store/api/public/v1/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.store.api.public.v1.views import (
    PublicStoreViewSet,
    StoreViewSet,
)

app_name = "store_public_v1"

router = DefaultRouter()
router.register("stores", StoreViewSet, basename="store")
router.register("public-stores", PublicStoreViewSet, basename="public-store")

urlpatterns = [
    path("", include(router.urls)),
]
