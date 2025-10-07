# credit/api/public/v1/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from credit.api.public.v1.views import (
    CreditLimitViewSet,
    StatementViewSet,
    StatementLineViewSet,
    LoanRiskOTPRequestView,
    LoanRiskOTPVerifyView,
    LoanRiskReportCheckView,
    LoanRiskReportDetailView,
    LoanRiskReportListView,
    LoanRiskReportLatestView,
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
    # Loan risk validation endpoints
    path('loan-risk/otp/request/', LoanRiskOTPRequestView.as_view(), name='loan_risk_otp_request'),
    path('loan-risk/otp/verify/', LoanRiskOTPVerifyView.as_view(), name='loan_risk_otp_verify'),
    path('loan-risk/reports/', LoanRiskReportListView.as_view(), name='loan_risk_report_list'),
    path('loan-risk/reports/latest/', LoanRiskReportLatestView.as_view(), name='loan_risk_report_latest'),
    path('loan-risk/reports/<int:pk>/', LoanRiskReportDetailView.as_view(), name='loan_risk_report_detail'),
    path('loan-risk/reports/<int:report_id>/check/', LoanRiskReportCheckView.as_view(), name='loan_risk_report_check'),
]
