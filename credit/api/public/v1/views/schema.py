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

# Credit Limit Schema Decorators
credit_limit_list_schema = extend_schema_view(
    get=extend_schema(
        summary="List user's credit limits",
        description=(
            "Retrieve a list of all credit limits belonging to the authenticated user. "
            "Credit limits define the maximum amount a user can spend on credit and "
            "track their current usage and availability. Only active credit limits "
            "are returned."
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
                        }
                    )
                ]
            ),
        },
    )
)

credit_limit_detail_schema = extend_schema_view(
    get=extend_schema(
        summary="Get credit limit details",
        description=(
            "Retrieve detailed information about a specific credit limit. "
            "Only returns credit limits belonging to the authenticated user. "
            "Includes all limit information, usage statistics, and status details."
        ),
        tags=["Credit Limits"],
        parameters=[
            OpenApiParameter(
                name='id',
                type=int,
                location=OpenApiParameter.PATH,
                description='Unique integer identifier for the credit limit'
            ),
        ],
        responses={
            200: CreditLimitSerializer,
            401: OpenApiResponse(
                description="Authentication required",
                examples=[
                    OpenApiExample(
                        "Unauthorized",
                        value={
                            "detail": "Authentication credentials were not provided."
                        }
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Credit limit not found or doesn't belong to user",
                examples=[
                    OpenApiExample(
                        "Not Found",
                        value={"detail": "Not found."}
                    )
                ]
            ),
        },
    )
)

# Statement Schema Decorators
statement_list_schema = extend_schema_view(
    get=extend_schema(
        summary="List user's credit statements",
        description=(
            "Retrieve a list of all credit statements belonging to the authenticated user. "
            "Returns a lightweight view of statements without detailed line items for "
            "optimal performance. Statements are ordered by most recent first (year, month, created_at). "
            "Use the detail endpoint to get full statement information including all transactions."
        ),
        tags=["Credit Statements"],
        responses={
            200: StatementListSerializer(many=True),
            401: OpenApiResponse(
                description="Authentication required",
                examples=[
                    OpenApiExample(
                        "Unauthorized",
                        value={
                            "detail": "Authentication credentials were not provided."
                        }
                    )
                ]
            ),
        },
        examples=[
            OpenApiExample(
                "Statement List Response",
                value=[
                    {
                        "id": 1,
                        "user": 123,
                        "year": 1403,
                        "month": 8,
                        "reference_code": "ST-1403-08-001",
                        "status": "current",
                        "opening_balance": 0,
                        "closing_balance": 150000,
                        "total_debit": 200000,
                        "total_credit": 50000,
                        "grace_date": "2024-11-15T23:59:59Z",
                        "created_at": "2024-11-01T00:00:00Z",
                        "updated_at": "2024-11-10T12:30:00Z"
                    }
                ]
            )
        ]
    )
)

statement_detail_schema = extend_schema_view(
    get=extend_schema(
        summary="Get credit statement details",
        description=(
            "Retrieve detailed information about a specific credit statement including "
            "all statement lines (transactions). Only returns statements belonging to "
            "the authenticated user. This endpoint provides complete statement information "
            "including all purchases, payments, fees, and penalties."
        ),
        tags=["Credit Statements"],
        parameters=[
            OpenApiParameter(
                name='id',
                type=int,
                location=OpenApiParameter.PATH,
                description='Unique integer identifier for the credit statement'
            ),
        ],
        responses={
            200: StatementDetailSerializer,
            401: OpenApiResponse(
                description="Authentication required",
                examples=[
                    OpenApiExample(
                        "Unauthorized",
                        value={
                            "detail": "Authentication credentials were not provided."
                        }
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Statement not found or doesn't belong to user",
                examples=[
                    OpenApiExample(
                        "Not Found",
                        value={"detail": "Not found."}
                    )
                ]
            ),
        },
        examples=[
            OpenApiExample(
                "Statement Detail Response",
                value={
                    "id": 1,
                    "user": 123,
                    "year": 1403,
                    "month": 8,
                    "reference_code": "ST-1403-08-001",
                    "status": "pending_payment",
                    "opening_balance": 0,
                    "closing_balance": 150000,
                    "total_debit": 200000,
                    "total_credit": 50000,
                    "grace_date": "2024-11-15T23:59:59Z",
                    "paid_at": None,
                    "closed_at": "2024-11-01T00:00:00Z",
                    "created_at": "2024-11-01T00:00:00Z",
                    "updated_at": "2024-11-10T12:30:00Z",
                    "lines": [
                        {
                            "id": 1,
                            "statement": 1,
                            "type": "purchase",
                            "amount": 100000,
                            "transaction": 456,
                            "description": "Online purchase",
                            "created_at": "2024-11-02T10:15:00Z"
                        },
                        {
                            "id": 2,
                            "statement": 1,
                            "type": "payment",
                            "amount": -50000,
                            "transaction": 789,
                            "description": "Payment received",
                            "created_at": "2024-11-05T14:30:00Z"
                        }
                    ]
                }
            )
        ]
    )
)

# Statement Line Schema Decorators
statement_line_list_schema = extend_schema_view(
    get=extend_schema(
        summary="List user's statement lines",
        description=(
            "Retrieve a list of all statement lines (transactions) belonging to the "
            "authenticated user. Statement lines represent individual transactions "
            "within credit statements including purchases, payments, fees, and penalties. "
            "Results are ordered by most recent first and can be filtered by statement_id."
        ),
        tags=["Statement Lines"],
        parameters=[
            OpenApiParameter(
                name='statement_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Filter lines by specific statement ID',
                required=False,
            ),
        ],
        responses={
            200: StatementLineSerializer(many=True),
            401: OpenApiResponse(
                description="Authentication required",
                examples=[
                    OpenApiExample(
                        "Unauthorized",
                        value={
                            "detail": "Authentication credentials were not provided."
                        }
                    )
                ]
            ),
        },
        examples=[
            OpenApiExample(
                "Statement Lines Response",
                value=[
                    {
                        "id": 1,
                        "statement": 1,
                        "type": "purchase",
                        "amount": 100000,
                        "transaction": 456,
                        "description": "Online purchase",
                        "created_at": "2024-11-02T10:15:00Z"
                    },
                    {
                        "id": 2,
                        "statement": 1,
                        "type": "payment",
                        "amount": -50000,
                        "transaction": 789,
                        "description": "Payment received",
                        "created_at": "2024-11-05T14:30:00Z"
                    }
                ]
            )
        ]
    )
)

# Purchase/Payment API Schema Decorators
add_purchase_schema = extend_schema(
    summary="Add purchase to credit statement",
    description=(
        "Add a purchase transaction to the user's current credit statement. "
        "If no current statement exists, a new one will be created automatically. "
        "The transaction must be valid and belong to the authenticated user. "
        "This endpoint processes the transaction and updates the statement balance."
    ),
    tags=["Credit Transactions"],
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "transaction_id": {
                    "type": "integer",
                    "description": "ID of the transaction to add as purchase"
                },
                "description": {
                    "type": "string",
                    "description": "Optional description for the purchase",
                    "default": ""
                }
            },
            "required": ["transaction_id"],
            "example": {
                "transaction_id": 12345,
                "description": "Online store purchase"
            }
        }
    },
    responses={
        201: OpenApiResponse(
            description="Purchase added successfully",
            examples=[
                OpenApiExample(
                    "Success",
                    value={"success": True}
                )
            ]
        ),
        400: OpenApiResponse(
            description="Bad request - validation error",
            examples=[
                OpenApiExample(
                    "Missing transaction_id",
                    value={"error": "transaction_id is required"}
                ),
                OpenApiExample(
                    "Invalid transaction",
                    value={"error": "Transaction validation failed"}
                )
            ]
        ),
        401: OpenApiResponse(
            description="Authentication required",
            examples=[
                OpenApiExample(
                    "Unauthorized",
                    value={
                        "detail": "Authentication credentials were not provided."
                    }
                )
            ]
        ),
        404: OpenApiResponse(
            description="Transaction not found",
            examples=[
                OpenApiExample(
                    "Not Found",
                    value={"detail": "Not found."}
                )
            ]
        ),
    },
)

add_payment_schema = extend_schema(
    summary="Add payment to credit statement",
    description=(
        "Apply a payment to the user's current credit statement. "
        "The payment amount must be positive and will be applied to reduce "
        "the outstanding balance. If a transaction_id is provided, it will "
        "be validated and linked to the payment record."
    ),
    tags=["Credit Transactions"],
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "integer",
                    "description": "Payment amount in smallest currency unit (Rials)"
                },
                "transaction_id": {
                    "type": "integer",
                    "description": "Optional ID of the transaction associated with payment"
                }
            },
            "required": ["amount"],
            "example": {
                "amount": 50000,
                "transaction_id": 67890
            }
        }
    },
    responses={
        201: OpenApiResponse(
            description="Payment applied successfully",
            examples=[
                OpenApiExample(
                    "Success",
                    value={"success": True, "applied_to": "current"}
                )
            ]
        ),
        400: OpenApiResponse(
            description="Bad request - validation error",
            examples=[
                OpenApiExample(
                    "Missing amount",
                    value={"error": "amount is required"}
                ),
                OpenApiExample(
                    "Invalid amount",
                    value={"error": "amount must be > 0"}
                ),
                OpenApiExample(
                    "No current statement",
                    value={"error": "No current statement"}
                )
            ]
        ),
        401: OpenApiResponse(
            description="Authentication required",
            examples=[
                OpenApiExample(
                    "Unauthorized",
                    value={
                        "detail": "Authentication credentials were not provided."
                    }
                )
            ]
        ),
    },
)

# Penalty and Statement Management Schema Decorators
apply_penalty_schema = extend_schema(
    summary="Apply penalty to overgrace statement",
    description=(
        "Apply penalty charges to the user's latest pending or overgrace statement. "
        "Penalties are calculated based on the overgrace amount and number of days "
        "past the grace_date. The penalty will be added as a new line item to the "
        "user's current statement."
    ),
    tags=["Credit Management"],
    responses={
        200: OpenApiResponse(
            description="Penalty applied successfully",
            examples=[
                OpenApiExample(
                    "Penalty Applied",
                    value={"penalty_applied": 15000}
                ),
                OpenApiExample(
                    "No Penalty",
                    value={"penalty_applied": 0}
                )
            ]
        ),
        400: OpenApiResponse(
            description="No pending or overgrace statement found",
            examples=[
                OpenApiExample(
                    "No Statement",
                    value={"error": "No pending or overgrace statement"}
                )
            ]
        ),
        401: OpenApiResponse(
            description="Authentication required",
            examples=[
                OpenApiExample(
                    "Unauthorized",
                    value={
                        "detail": "Authentication credentials were not provided."
                    }
                )
            ]
        ),
    },
)

close_statement_schema = extend_schema(
    summary="Close current credit statement",
    description=(
        "Close the user's current credit statement and transition it to "
        "pending_payment status. This action finalizes the statement for "
        "the current period and sets up the grace_date for payment. "
        "Only current statements can be closed."
    ),
    tags=["Credit Management"],
    responses={
        200: OpenApiResponse(
            description="Statement closed successfully",
            examples=[
                OpenApiExample(
                    "Success",
                    value={"success": True}
                )
            ]
        ),
        400: OpenApiResponse(
            description="No current statement to close",
            examples=[
                OpenApiExample(
                    "No Current Statement",
                    value={"error": "No current statement"}
                )
            ]
        ),
        401: OpenApiResponse(
            description="Authentication required",
            examples=[
                OpenApiExample(
                    "Unauthorized",
                    value={
                        "detail": "Authentication credentials were not provided."
                    }
                )
            ]
        ),
    },
)

risk_score_schema = extend_schema(
    summary="Get user's credit risk score",
    description=(
        "Calculate and retrieve the user's current credit risk score. "
        "The risk score is calculated based on payment history, outstanding "
        "balances, and other credit behavior factors. Higher scores indicate "
        "lower risk. This score is used for credit limit adjustments and "
        "risk management decisions."
    ),
    tags=["Credit Management"],
    responses={
        200: OpenApiResponse(
            description="Risk score calculated successfully",
            examples=[
                OpenApiExample(
                    "Risk Score",
                    value={"risk_score": 750}
                )
            ]
        ),
        401: OpenApiResponse(
            description="Authentication required",
            examples=[
                OpenApiExample(
                    "Unauthorized",
                    value={
                        "detail": "Authentication credentials were not provided."
                    }
                )
            ]
        ),
    },
)
