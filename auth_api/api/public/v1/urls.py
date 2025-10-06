# auth_api/api/public/v1/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from auth_api.api.public.v1.views import AuthViewSet

app_name = "auth_api_public_v1"

router = DefaultRouter()
router.register("", AuthViewSet, basename="auth")

urlpatterns = [
    path("", include(router.urls)),
]
