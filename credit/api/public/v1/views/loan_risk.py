# credit/api/public/v1/views/loan_risk.py
# Clean, modular ViewSets for Loan Risk flows (RESTful + actions)

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from credit.api.public.v1.schema import (
    otp_request_schema,
    otp_verify_schema,
    report_viewset_schema,
    report_latest_schema,
    report_check_schema,
)
from credit.api.public.v1.serializers import (
    LoanRiskOTPRequestSerializer,
    LoanRiskOTPVerifySerializer,
    LoanRiskReportSerializer,
    LoanRiskReportDetailSerializer,
    LoanRiskReportListSerializer,
)
from credit.models import LoanRiskReport
from credit.tasks_loan_validation import (
    send_loan_validation_otp,
    verify_loan_otp_and_request_report,
    check_loan_report_result,
)
from credit.utils.choices import LoanReportStatus
from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from profiles.models.profile import Profile


# ---------- Collection-level flows: OTP request/verify ----------

class LoanRiskAuthViewSet(
    ScopedThrottleByActionMixin,
    viewsets.GenericViewSet
):
    """
    Collection-level authentication actions for loan risk:
    - POST /loan-risk/otp/request/
    - POST /loan-risk/otp/verify/
    """
    permission_classes = [IsAuthenticated]
    throttle_scope_map = {
        "default": "loan-risk",
        "otp_request": "loan-risk-otp",
        "otp_verify": "loan-risk-otp",
    }

    def _ok(self, payload, code=status.HTTP_200_OK):
        return Response(payload, status=code)

    @otp_request_schema
    @action(detail=False, methods=["post"], url_path="otp/request")
    def otp_request(self, request):
        """Validate eligibility → create report → send OTP."""
        ser = LoanRiskOTPRequestSerializer(
            data=request.data, context={"request": request}
        )
        ser.is_valid(raise_exception=True)

        profile = ser.validated_data["_profile"]

        report = LoanRiskReport.objects.create(
            profile=profile,
            national_code=profile.national_id,
            mobile_number=profile.phone_number,
        )
        task = send_loan_validation_otp.delay(report.id)

        return self._ok(
            {
                "success": True,
                "message": "OTP will be sent shortly.",
                "report_id": report.id,
                "task_id": task.id,
            }
        )

    @otp_verify_schema
    @action(detail=False, methods=["post"], url_path="otp/verify")
    def otp_verify(self, request):
        """Verify OTP with provider and request credit report."""
        ser = LoanRiskOTPVerifySerializer(
            data=request.data, context={"request": request}
        )
        ser.is_valid(raise_exception=True)

        report_id = ser.validated_data["report_id"]
        otp_code = ser.validated_data["otp_code"]

        task = verify_loan_otp_and_request_report.delay(report_id, otp_code)

        return self._ok(
            {
                "success": True,
                "message": "OTP verified. Report is being generated.",
                "report_id": report_id,
                "task_id": task.id,
            }
        )


# ---------- Resource: Reports (list/retrieve + latest + check) ----------

@report_viewset_schema
class LoanRiskReportViewSet(
    ScopedThrottleByActionMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    """
    LoanRiskReport endpoints:
    - GET    /loan-risk/reports/              (list)
    - GET    /loan-risk/reports/{id}/         (retrieve)
    - GET    /loan-risk/reports/latest/       (collection action)
    - POST   /loan-risk/reports/{id}/check/   (detail action)
    """
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"
    throttle_scope_map = {
        "default": "loan-risk-reports",
        "list": "loan-risk-reports",
        "retrieve": "loan-risk-reports",
        "latest": "loan-risk-reports",
        "check": "loan-risk-reports",
    }

    def get_queryset(self):
        profile = get_object_or_404(Profile, user=self.request.user)
        return LoanRiskReport.objects.filter(profile=profile).order_by(
            "-created_at"
        )

    def get_serializer_class(self):
        if self.action == "list":
            return LoanRiskReportListSerializer
        if self.action in {"retrieve"}:
            return LoanRiskReportDetailSerializer
        # Fallback for actions that return a report shape
        return LoanRiskReportSerializer

    @report_latest_schema
    @action(detail=False, methods=["get"], url_path="latest")
    def latest(self, request):
        """Return the latest report for the current user."""
        profile = get_object_or_404(Profile, user=request.user)
        report = (
            LoanRiskReport.objects
            .filter(profile=profile)
            .order_by("-created_at")
            .first()
        )
        if not report:
            return Response(
                {"error": "No report found"}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(
            LoanRiskReportSerializer(report).data, status=status.HTTP_200_OK
        )

    @report_check_schema
    @action(detail=True, methods=["post"], url_path="check")
    def check(self, request, pk=None):
        """
        If COMPLETED → return the report.
        If can_check_result() → trigger background task and return task_id.
        Else → return current status payload.
        """
        report = self.get_object()

        if report.status == LoanReportStatus.COMPLETED:
            return Response(
                LoanRiskReportSerializer(report).data,
                status=status.HTTP_200_OK
            )

        if report.can_check_result():
            task = check_loan_report_result.delay(report.id)
            return Response(
                {
                    "success": True,
                    "message": "Report check scheduled.",
                    "task_id": task.id,
                    "status": report.get_status_display(),
                }, status=status.HTTP_200_OK
            )

        return Response(
            LoanRiskReportSerializer(report).data, status=status.HTTP_200_OK
        )
