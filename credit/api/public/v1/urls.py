# credit/api/public/v1/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from credit.api.public.v1.views import (
    CreditLimitViewSet,
    StatementViewSet,
    StatementLineViewSet,
)

app_name = "credit_public_v1"

router = DefaultRouter()
router.register("credit-limits", CreditLimitViewSet, basename="credit-limit")
router.register("statements", StatementViewSet, basename="statement")
router.register(
    "statement-lines", StatementLineViewSet, basename="statement-line"
)

urlpatterns = [
    path("", include(router.urls)),
]
