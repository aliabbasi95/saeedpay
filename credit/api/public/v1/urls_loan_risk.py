# credit/api/public/v1/urls_loan_risk.py

from django.urls import path
from credit.api.public.v1.views.loan_risk_views import (
    LoanRiskOTPRequestView,
    LoanRiskOTPVerifyView,
    LoanRiskReportCheckView,
    LoanRiskReportDetailView,
    LoanRiskReportListView,
    LoanRiskReportLatestView,
)

app_name = 'loan_risk'

urlpatterns = [
    # OTP flow
    path('otp/request/', LoanRiskOTPRequestView.as_view(), name='otp-request'),
    path('otp/verify/', LoanRiskOTPVerifyView.as_view(), name='otp-verify'),
    
    # Report management
    path('reports/', LoanRiskReportListView.as_view(), name='report-list'),
    path('reports/latest/', LoanRiskReportLatestView.as_view(), name='report-latest'),
    path('reports/<int:pk>/', LoanRiskReportDetailView.as_view(), name='report-detail'),
    path('reports/<int:report_id>/check/', LoanRiskReportCheckView.as_view(), name='report-check'),
]
