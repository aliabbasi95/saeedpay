# credit/api/public/v1/schema/loan_risk.py

from drf_spectacular.utils import extend_schema, extend_schema_view

from credit.api.public.v1.serializers import (
    LoanRiskOTPRequestSerializer,
    LoanRiskOTPVerifySerializer,
    LoanRiskReportSerializer,
    LoanRiskReportDetailSerializer,
    LoanRiskReportListSerializer,
)

loan_risk_otp_request_schema = extend_schema(
    tags=["Credit · Loan Risk"],
    summary="Request OTP for loan risk validation",
    description="""
    Initiates the loan risk validation process by sending an OTP to the user's registered mobile number.

    **Requirements:**
    - User must be authenticated
    - User must have completed identity verification (auth_stage = 3)
    - User must have national_id and phone_number in profile
    - At least 30 days must have passed since last report (if any)

    **Process:**
    1. Validates user eligibility
    2. Creates a new LoanRiskReport record
    3. Sends OTP to user's mobile number
    4. Returns task_id for tracking
    """,
    request=LoanRiskOTPRequestSerializer,
    responses={
        200: {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "example": True},
                "message": {"type": "string"},
                "task_id": {"type": "string"},
            }
        },
        400: {
            "type": "object",
            "properties": {
                "non_field_errors": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        }
    }
)

loan_risk_otp_verify_schema = extend_schema(
    tags=["Credit · Loan Risk"],
    summary="Verify OTP and request loan risk report",
    description="""
    Verifies the OTP code and initiates the credit report generation process.

    **Requirements:**
    - User must be authenticated
    - Valid report_id that belongs to the user
    - Valid OTP code
    - Report must be in OTP_SENT status

    **Process:**
    1. Validates OTP code with provider
    2. If valid, requests credit report generation
    3. Updates report status to REPORT_REQUESTED
    4. Returns task_id for tracking report generation
    """,
    request=LoanRiskOTPVerifySerializer,
    responses={
        200: {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "example": True},
                "message": {"type": "string"},
                "report_id": {"type": "integer"},
                "task_id": {"type": "string"},
            }
        },
        400: {
            "type": "object",
            "properties": {
                "report_id": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "otp_code": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        }
    }
)

loan_risk_report_list_schema = extend_schema_view(
    get=extend_schema(
        tags=["Credit · Loan Risk"],
        summary="List user's loan risk reports",
        description="""
        Returns a list of all loan risk reports belonging to the authenticated user,
        ordered by creation date (newest first).
        """,
        responses={200: LoanRiskReportListSerializer(many=True)},
    )
)

loan_risk_report_detail_schema = extend_schema_view(
    get=extend_schema(
        tags=["Credit · Loan Risk"],
        summary="Get detailed loan risk report",
        description="""
        Returns detailed information about a specific loan risk report,
        including full report data JSON.

        **Requirements:**
        - Report must belong to the authenticated user
        """,
        responses={200: LoanRiskReportDetailSerializer},
    )
)

loan_risk_report_latest_schema = extend_schema(
    tags=["Credit · Loan Risk"],
    summary="Get user's latest loan risk report",
    description="""
    Returns the most recently created loan risk report for the authenticated user.

    **Returns:**
    - Latest report if exists
    - 404 if no reports found
    """,
    responses={
        200: LoanRiskReportSerializer,
        404: {
            "type": "object",
            "properties": {
                "error": {"type": "string"}
            }
        }
    }
)

loan_risk_report_check_schema = extend_schema(
    tags=["Credit · Loan Risk"],
    summary="Check loan risk report status",
    description="""
    Checks the status of a loan risk report and retrieves results if available.

    **Behavior:**
    - If report is COMPLETED: Returns full report data
    - If report can check result: Triggers background check and returns task_id
    - Otherwise: Returns current report status

    **Requirements:**
    - Report must belong to the authenticated user
    """,
    responses={
        200: LoanRiskReportSerializer,
        404: {
            "type": "object",
            "properties": {
                "error": {"type": "string"}
            }
        }
    }
)
