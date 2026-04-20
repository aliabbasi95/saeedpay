# credit/api/public/v1/schema/loan_risk.py

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from credit.api.public.v1.serializers import (
    LoanRiskOTPRequestSerializer,
    LoanRiskOTPVerifySerializer,
    LoanRiskReportDetailSerializer,
    LoanRiskReportListSerializer,
    LoanRiskReportSerializer,
)

otp_request_schema = extend_schema(
    tags=["Credit · Loan Risk"],
    summary="Request OTP for loan risk validation",
    description=(
        "Start the loan risk validation flow by sending an OTP to the user's "
        "registered phone number."
    ),
    request=LoanRiskOTPRequestSerializer,
    responses={
        200: OpenApiResponse(
            description="OTP request accepted.",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "success": True,
                        "message": "OTP will be sent shortly.",
                        "report_id": 123,
                        "task_id": "3c2a7e5f-...",
                    },
                )
            ],
        ),
        400: OpenApiResponse(description="Validation error or user is not eligible."),
        429: OpenApiResponse(description="Too many requests."),
    },
)

otp_verify_schema = extend_schema(
    tags=["Credit · Loan Risk"],
    summary="Verify OTP and request loan risk report",
    description=(
        "Verify the OTP with the provider and trigger loan risk report generation."
    ),
    request=LoanRiskOTPVerifySerializer,
    responses={
        200: OpenApiResponse(
            description="OTP verified and report generation started.",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "success": True,
                        "message": "OTP verified. Report is being generated.",
                        "report_id": 123,
                        "task_id": "f0b6a1a9-...",
                    },
                )
            ],
        ),
        400: OpenApiResponse(description="Validation error."),
        404: OpenApiResponse(description="Report not found."),
    },
)

report_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=["Credit · Loan Risk"],
        summary="List user's loan risk reports",
        description=(
            "Return all loan risk reports for the authenticated user, "
            "ordered from newest to oldest."
        ),
        responses={200: LoanRiskReportListSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["Credit · Loan Risk"],
        summary="Retrieve a loan risk report",
        description="Return a single loan risk report belonging to the authenticated user.",
        parameters=[
            OpenApiParameter(
                name="id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Loan risk report id.",
            ),
        ],
        responses={200: LoanRiskReportDetailSerializer},
    ),
)

report_latest_schema = extend_schema(
    tags=["Credit · Loan Risk"],
    summary="Get latest loan risk report",
    description="Return the most recent loan risk report for the authenticated user.",
    responses={
        200: LoanRiskReportSerializer,
        404: OpenApiResponse(description="No report found."),
    },
)

report_check_schema = extend_schema(
    tags=["Credit · Loan Risk"],
    summary="Check report status",
    description=(
        "If the report is completed, return the report. "
        "If the report can be checked, enqueue a background task and return its task id. "
        "Otherwise return the current report payload."
    ),
    parameters=[
        OpenApiParameter(
            name="id",
            location=OpenApiParameter.PATH,
            type=OpenApiTypes.INT,
            description="Loan risk report id.",
        ),
    ],
    responses={
        200: LoanRiskReportSerializer,
        404: OpenApiResponse(description="Report not found."),
    },
)
