# store/api/public/v1/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from store.api.public.v1.views import (
    StoreViewSet,
    PublicStoreViewSet,
)

app_name = "store_public_v1"

router = DefaultRouter()
router.register("stores", StoreViewSet, basename="store")
router.register("public-stores", PublicStoreViewSet, basename="public-store")

urlpatterns = [
    path("", include(router.urls)),
]
