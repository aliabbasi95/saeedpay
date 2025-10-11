# credit/api/public/v1/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from credit.api.public.v1.views import (
    CreditLimitViewSet,
    StatementViewSet,
    StatementLineViewSet,
)
from credit.api.public.v1.views import (
    LoanRiskAuthViewSet,
    LoanRiskReportViewSet,
)

app_name = "credit_public_v1"

router = DefaultRouter()
router.register("credit-limits", CreditLimitViewSet, basename="credit-limit")
router.register("statements", StatementViewSet, basename="statement")
router.register(
    "statement-lines", StatementLineViewSet, basename="statement-line"
)
router.register("loan-risk", LoanRiskAuthViewSet, basename="loan-risk-auth")
router.register(
    "loan-risk/reports", LoanRiskReportViewSet, basename="loan-risk-report"
)

urlpatterns = [
    path("", include(router.urls)),
]
