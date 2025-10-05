# kyc/api/public/v1/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views.identity_verification import IdentityVerificationViewSet
from .views.video_verification import VideoVerificationViewSet

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
