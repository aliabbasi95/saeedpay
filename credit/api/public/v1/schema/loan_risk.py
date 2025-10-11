# credit/api/public/v1/schema/loan_risk.py
# Swagger schema decorators for Loan Risk endpoints (clean, modular, with examples)

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    extend_schema, extend_schema_view,
    OpenApiExample, OpenApiResponse, OpenApiParameter,
)

from credit.api.public.v1.serializers import (
    LoanRiskOTPRequestSerializer,
    LoanRiskOTPVerifySerializer,
    LoanRiskReportSerializer,
    LoanRiskReportDetailSerializer,
    LoanRiskReportListSerializer,
)

# ----- OTP (collection actions on Auth ViewSet) -----

otp_request_schema = extend_schema(
    tags=["Credit · Loan Risk"],
    summary="Request OTP for loan risk validation",
    description=(
        "Starts loan risk validation by sending an OTP to the user's registered phone.\n\n"
        "**Requirements**\n"
        "- Authenticated user\n"
        "- Identity verification completed (auth_stage=3)\n"
        "- Profile has national_id and phone_number\n"
        "- At least 30 days since last completed report\n"
    ),
    request=LoanRiskOTPRequestSerializer,
    responses={
        200: OpenApiResponse(
            description="OTP request accepted",
            examples=[OpenApiExample(
                "OK",
                value={
                    "success": True,
                    "message": "OTP will be sent shortly.",
                    "report_id": 123,
                    "task_id": "3c2a7e5f-..."
                }
            )],
        ),
        400: OpenApiResponse(description="Validation error or not eligible"),
        429: OpenApiResponse(description="Too many requests (cooldown)"),
    },
)

otp_verify_schema = extend_schema(
    tags=["Credit · Loan Risk"],
    summary="Verify OTP and request loan risk report",
    description=(
        "Verifies OTP with the provider and triggers report generation.\n\n"
        "**Requirements**\n"
        "- Authenticated user\n"
        "- Valid `report_id` belonging to the user\n"
        "- Report status is `OTP_SENT`"
    ),
    request=LoanRiskOTPVerifySerializer,
    responses={
        200: OpenApiResponse(
            description="OTP verified, report requested",
            examples=[OpenApiExample(
                "OK",
                value={
                    "success": True,
                    "message": "OTP verified. Report is being generated.",
                    "report_id": 123,
                    "task_id": "f0b6a1a9-..."
                }
            )],
        ),
        400: OpenApiResponse(description="Validation error"),
        404: OpenApiResponse(description="Report not found"),
    },
)

# ----- Reports (ViewSet: list/retrieve + actions) -----

report_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=["Credit · Loan Risk"],
        summary="List user's loan risk reports",
        description="Returns all reports for the authenticated user (newest first).",
        responses={200: LoanRiskReportListSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["Credit · Loan Risk"],
        summary="Retrieve a loan risk report",
        description="Returns a single report (belongs to the current user).",
        responses={200: LoanRiskReportDetailSerializer},
    ),
)

report_latest_schema = extend_schema(
    tags=["Credit · Loan Risk"],
    summary="Get latest loan risk report",
    description="Returns the most recently created report; 404 if none exists.",
    responses={
        200: LoanRiskReportSerializer,
        404: OpenApiResponse(description="No report found"),
    },
)

report_check_schema = extend_schema(
    tags=["Credit · Loan Risk"],
    summary="Check report status (and fetch if ready)",
    description=(
        "Checks the status of a report:\n"
        "- If COMPLETED → returns full report\n"
        "- If can check result → triggers background check and returns task_id\n"
        "- Otherwise → returns current status\n\n"
        "Report must belong to the current user."
    ),
    parameters=[
        OpenApiParameter(
            name="id",
            location=OpenApiParameter.PATH,
            type=OpenApiTypes.INT,
            description="Report id",
        ),
    ],
    responses={
        200: LoanRiskReportSerializer,
        404: OpenApiResponse(description="Report not found"),
    },
)
