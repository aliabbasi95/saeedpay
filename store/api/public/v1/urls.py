# store/api/public/v1/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from store.api.public.v1.views import StoreApiKeyRegenerateView, StoreViewSet

app_name = "store_public_v1"

router = DefaultRouter()
router.register("store", StoreViewSet, basename="store")

urlpatterns = [
    path(
        "regenerate-api-key/",
        StoreApiKeyRegenerateView.as_view(),
        name="regenerate-api-key"
    ),
    path("", include(router.urls)),
]
