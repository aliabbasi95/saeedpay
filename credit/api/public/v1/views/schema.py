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

# ---------- Credit Limit ----------

credit_limit_list_schema = extend_schema_view(
    get=extend_schema(
        summary="List user's credit limits",
        description=(
            "Retrieve all credit limits belonging to the authenticated user. "
            "Each credit limit exposes approved_limit, availability, status and expiry."
        ),
        tags=["Credit Limits"],
        responses={
            200: CreditLimitSerializer(many=True),
            401: OpenApiResponse(
                description="Authentication required",
                examples=[OpenApiExample(
                    "Unauthorized", value={
                        "detail": "Authentication credentials were not provided."
                    }
                )],
            ),
        },
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

statement_list_schema = extend_schema_view(
    get=extend_schema(
        summary="List user's credit statements",
        description=(
            "Retrieve all statements of the authenticated user. "
            "Ordered by most recent first. This is a lightweight view (no lines)."
        ),
        tags=["Credit Statements"],
        responses={
            200: StatementListSerializer(many=True),
            401: OpenApiResponse(description="Authentication required"),
        },
        examples=[
            OpenApiExample(
                "Example",
                value=[{
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
                    "updated_at": "2024-11-10T12:30:00Z"
                }]
            )
        ],
    )
)

statement_detail_schema = extend_schema_view(
    get=extend_schema(
        summary="Get a credit statement with lines",
        description=(
            "Retrieve a single statement (owned by the user) including all statement lines."
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
                "Example",
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
                            "created_at": "2024-11-02T10:15:00Z"
                        },
                        {
                            "id": 2,
                            "statement": 17,
                            "type": "payment",
                            "amount": 50000,
                            "transaction": 789,
                            "description": "Payment received",
                            "created_at": "2024-11-05T14:30:00Z"
                        }
                    ]
                }
            )
        ],
    )
)

# ---------- Statement Lines ----------

statement_line_list_schema = extend_schema_view(
    get=extend_schema(
        summary="List user's statement lines",
        description=(
            "List statement lines owned by the authenticated user. "
            "Filterable by ?statement_id=..."
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
            401: OpenApiResponse(description="Authentication required"),
        },
    )
)

# ---------- Transactions on Statements ----------

add_purchase_schema = extend_schema(
    summary="Record a purchase from a successful transaction",
    description=(
        "Append a PURCHASE line to the current statement of the buyer "
        "(owner of transaction.from_wallet). The transaction must be SUCCESS "
        "and belong to the authenticated user."
    ),
    tags=["Credit Transactions"],
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "integer"},
                "description": {
                    "type": "string",
                    "default": "Purchase"
                },
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
        "Append a PAYMENT line to the CURRENT statement. Positive amount required. "
        "If transaction_id is provided, it must be SUCCESS and belong to the user."
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
        "Sets due_date based on active credit limit."
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
