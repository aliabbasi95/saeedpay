# kyc/api/public/v1/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import IdentityVerificationViewSet, VideoVerificationViewSet

app_name = "kyc_public_v1"

router = DefaultRouter()
router.register(
    "verify-identity", IdentityVerificationViewSet, basename="verify-identity"
)
router.register(
    "video", VideoVerificationViewSet, basename="video-verification"
)

urlpatterns = [
    path("", include(router.urls)),
]
