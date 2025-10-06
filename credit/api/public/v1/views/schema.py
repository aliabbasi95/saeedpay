# credit/api/public/v1/views/schema.py

from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiExample,
)

from credit.api.public.v1.serializers.credit import (
    CreditLimitSerializer,
    StatementListSerializer,
    StatementDetailSerializer,
    StatementLineSerializer,
)
from credit.api.public.v1.serializers.loan_risk_serializers import (
    LoanRiskOTPRequestSerializer,
    LoanRiskOTPVerifySerializer,
    LoanRiskReportSerializer,
    LoanRiskReportDetailSerializer,
    LoanRiskReportListSerializer,
)

# ---------- Credit Limits ----------

# List is UNPAGINATED (pagination_class=None in the view)
credit_limit_list_schema = extend_schema_view(
    get=extend_schema(
        summary="List user's credit limits",
        description=(
            "Retrieve all credit limits belonging to the authenticated user. "
            "Each item includes approved_limit, available_limit, status and expiry."
        ),
        tags=["Credit Limits"],
        responses={
            200: CreditLimitSerializer(many=True),
            401: OpenApiResponse(
                description="Authentication required",
                examples=[
                    OpenApiExample(
                        "Unauthorized",
                        value={
                            "detail": "Authentication credentials were not provided."
                        },
                    )
                ],
            ),
        },
        examples=[
            OpenApiExample(
                "Success (unpaginated)",
                value=[
                    {
                        "id": 10,
                        "user": 123,
                        "approved_limit": 2000000,
                        "available_limit": 1500000,
                        "is_active": True,
                        "is_approved": True,
                        "expiry_date": "2026-09-06",
                        "created_at": "2025-09-01T08:00:00Z",
                        "updated_at": "2025-09-06T08:00:00Z",
                    }
                ],
            )
        ],
    )
)

credit_limit_detail_schema = extend_schema_view(
    get=extend_schema(
        summary="Get a credit limit",
        description="Retrieve a single credit limit owned by the authenticated user.",
        tags=["Credit Limits"],
        parameters=[
            OpenApiParameter(
                name="pk",
                type=int,
                location=OpenApiParameter.PATH,
                description="Primary key of the credit limit",
            ),
        ],
        responses={
            200: CreditLimitSerializer,
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Not found"),
        },
    )
)

# ---------- Statements ----------

# List is PAGINATED (uses project default pagination)
statement_list_schema = extend_schema_view(
    get=extend_schema(
        summary="List user's credit statements",
        description=(
            "Paginated list of statements belonging to the authenticated user. "
            "Ordered by most recent first (year, month, created_at descending). "
            "This is a lightweight list (does not include lines)."
        ),
        tags=["Credit Statements"],
        responses={
            200: StatementListSerializer(many=True),
            # drf-spectacular wraps in pagination schema
            401: OpenApiResponse(description="Authentication required"),
        },
        examples=[
            OpenApiExample(
                "Success (paginated)",
                value={
                    "count": 23,
                    "next": "https://api.example.com/credit/statements/?page=2",
                    "previous": None,
                    "results": [
                        {
                            "id": 17,
                            "user": 123,
                            "year": 1403,
                            "month": 8,
                            "reference_code": "ST-1403-08-001",
                            "status": "pending_payment",
                            "opening_balance": 0,
                            "closing_balance": -150000,
                            "total_debit": 200000,
                            "total_credit": 50000,
                            "due_date": "2024-11-15T23:59:59Z",
                            "created_at": "2024-11-01T00:00:00Z",
                            "updated_at": "2024-11-10T12:30:00Z",
                        }
                    ],
                },
            )
        ],
    )
)

statement_detail_schema = extend_schema_view(
    get=extend_schema(
        summary="Get a credit statement with lines",
        description=(
            "Retrieve a single statement (owned by the user) including its statement lines."
        ),
        tags=["Credit Statements"],
        parameters=[
            OpenApiParameter(
                name="pk",
                type=int,
                location=OpenApiParameter.PATH,
                description="Primary key of the statement",
            ),
        ],
        responses={
            200: StatementDetailSerializer,
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Not found"),
        },
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "id": 17,
                    "user": 123,
                    "year": 1403,
                    "month": 8,
                    "reference_code": "ST-1403-08-001",
                    "status": "pending_payment",
                    "opening_balance": 0,
                    "closing_balance": -150000,
                    "total_debit": 200000,
                    "total_credit": 50000,
                    "due_date": "2024-11-15T23:59:59Z",
                    "paid_at": None,
                    "closed_at": "2024-11-01T00:00:00Z",
                    "created_at": "2024-11-01T00:00:00Z",
                    "updated_at": "2024-11-10T12:30:00Z",
                    "lines": [
                        {
                            "id": 1,
                            "statement": 17,
                            "type": "purchase",
                            "amount": -100000,
                            "transaction": 456,
                            "description": "Online purchase",
                            "created_at": "2024-11-02T10:15:00Z",
                        },
                        {
                            "id": 2,
                            "statement": 17,
                            "type": "payment",
                            "amount": 50000,
                            "transaction": 789,
                            "description": "Payment received",
                            "created_at": "2024-11-05T14:30:00Z",
                        },
                    ],
                },
            )
        ],
    )
)

# ---------- Statement Lines ----------

# List is PAGINATED, optional ?statement_id=... (string values are tolerated but non-integers yield empty result)
statement_line_list_schema = extend_schema_view(
    get=extend_schema(
        summary="List user's statement lines",
        description=(
            "Paginated list of statement lines belonging to the authenticated user. "
            "Optionally filter by a specific statement using the 'statement_id' query parameter. "
            "If 'statement_id' is not a valid integer, an empty result is returned."
        ),
        tags=["Statement Lines"],
        parameters=[
            OpenApiParameter(
                name="statement_id",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Filter by a specific statement id",
                required=False,
            ),
        ],
        responses={
            200: StatementLineSerializer(many=True),
            # wrapped in pagination schema
            401: OpenApiResponse(description="Authentication required"),
        },
        examples=[
            OpenApiExample(
                "Success (paginated)",
                value={
                    "count": 3,
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": 101,
                            "statement": 17,
                            "type": "purchase",
                            "amount": -250000,
                            "transaction": 999,
                            "description": "POS purchase",
                            "created_at": "2024-11-02T10:15:00Z",
                        }
                    ],
                },
            ),
            OpenApiExample(
                "Filtered with non-integer statement_id (empty)",
                value={
                    "count": 0, "next": None, "previous": None, "results": []
                },
            ),
        ],
    )
)

# ---------- Transactions on Statements ----------

add_purchase_schema = extend_schema(
    summary="Record a purchase from a successful transaction",
    description=(
        "Append a PURCHASE line to the CURRENT statement of the buyer "
        "(owner of transaction.from_wallet). The transaction must be SUCCESS "
        "and belong to the authenticated user."
    ),
    tags=["Credit Transactions"],
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "integer"},
                "description": {"type": "string", "default": "Purchase"},
            },
            "required": ["transaction_id"],
        }
    },
    responses={
        201: OpenApiResponse(
            description="Recorded",
            examples=[OpenApiExample("OK", value={"success": True})],
        ),
        400: OpenApiResponse(description="Validation error"),
        401: OpenApiResponse(description="Authentication required"),
        404: OpenApiResponse(description="Transaction not found"),
    },
)

add_payment_schema = extend_schema(
    summary="Record a payment on the current statement",
    description=(
        "Append a PAYMENT line to the CURRENT statement. Positive amount is required. "
        "If 'transaction_id' is provided, it must be SUCCESS and belong to the user."
    ),
    tags=["Credit Transactions"],
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "amount": {"type": "integer"},
                "transaction_id": {"type": "integer"},
                "description": {"type": "string", "default": "Payment"},
            },
            "required": ["amount"],
        }
    },
    responses={
        201: OpenApiResponse(
            description="Recorded",
            examples=[OpenApiExample("OK", value={"success": True})],
        ),
        400: OpenApiResponse(description="Validation error"),
        401: OpenApiResponse(description="Authentication required"),
    },
)

close_statement_schema = extend_schema(
    summary="Close the current statement",
    description=(
        "Close the CURRENT statement and move it to PENDING_PAYMENT. "
        "The due_date will be set based on the active credit limit."
    ),
    tags=["Credit Management"],
    responses={
        200: OpenApiResponse(
            description="Closed",
            examples=[OpenApiExample("OK", value={"success": True})],
        ),
        400: OpenApiResponse(description="No current statement"),
        401: OpenApiResponse(description="Authentication required"),
    },
)

# ---------- Loan Risk Validation ----------

loan_risk_otp_request_schema = extend_schema(
    tags=["Loan Risk"],
    summary="درخواست کد یکبار مصرف برای اعتبارسنجی وام",
    description="ارسال کد یکبار مصرف به شماره موبایل کاربر برای شروع فرآیند اعتبارسنجی",
    request=LoanRiskOTPRequestSerializer,
    responses={
        200: {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "message": {"type": "string"},
                "report_id": {"type": "integer"},
            },
        },
    },
)

loan_risk_otp_verify_schema = extend_schema(
    tags=["Loan Risk"],
    summary="تایید کد و درخواست گزارش اعتبارسنجی",
    description="تایید کد یکبار مصرف و درخواست تولید گزارش اعتباری",
    request=LoanRiskOTPVerifySerializer,
    responses={
        200: {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "message": {"type": "string"},
                "report_id": {"type": "integer"},
            },
        },
    },
)

loan_risk_report_check_schema = extend_schema(
    tags=["Loan Risk"],
    summary="بررسی وضعیت گزارش اعتبارسنجی",
    description="بررسی وضعیت گزارش و دریافت نتیجه در صورت آماده بودن",
    responses={
        200: LoanRiskReportSerializer,
    },
)

loan_risk_report_detail_schema = extend_schema(
    tags=["Loan Risk"],
    summary="مشاهده جزئیات کامل گزارش اعتبارسنجی",
    description="دریافت اطلاعات کامل گزارش اعتبارسنجی شامل داده‌های JSON",
)

loan_risk_report_list_schema = extend_schema(
    tags=["Loan Risk"],
    summary="لیست گزارش‌های اعتبارسنجی",
    description="مشاهده تمام گزارش‌های اعتبارسنجی کاربر",
)

loan_risk_report_latest_schema = extend_schema(
    tags=["Loan Risk"],
    summary="آخرین گزارش اعتبارسنجی",
    description="دریافت آخرین گزارش اعتبارسنجی کاربر",
    responses={
        200: LoanRiskReportSerializer,
        404: {
            "type": "object",
            "properties": {
                "error": {"type": "string"},
            },
        },
    },
)
