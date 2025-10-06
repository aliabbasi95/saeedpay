# credit/api/public/v1/schema/statement.py

from drf_spectacular.utils import (
    extend_schema, extend_schema_view,
    OpenApiResponse, OpenApiExample, OpenApiParameter, OpenApiTypes,
)

from credit.api.public.v1.serializers.credit import (
    StatementListSerializer,
    StatementDetailSerializer,
    CloseStatementResponseSerializer,
)

statement_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=["Credit · Statements"],
        summary="List user's statements",
        description="Paginated list ordered by `-year, -month, -created_at`.",
        parameters=[
            OpenApiParameter(
                name="ordering",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                required=False,
                description="Optional ordering, default is most recent first",
                examples=[OpenApiExample(
                    "Default", value="-year,-month,-created_at"
                )],
            ),
        ],
        responses={200: StatementListSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["Credit · Statements"],
        summary="Retrieve a statement (with lines)",
        responses={200: StatementDetailSerializer},
    ),
)

add_purchase_schema = extend_schema(
    tags=["Credit · Transactions"],
    summary="Record a purchase from a successful transaction",
    description=(
        "Append a PURCHASE line to CURRENT statement of the buyer "
        "(transaction.from_wallet owner). Transaction must be SUCCESS and belong to the user."
    ),
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
        403: OpenApiResponse(description="Not allowed"),
        404: OpenApiResponse(description="Transaction not found"),
    },
)

add_payment_schema = extend_schema(
    tags=["Credit · Transactions"],
    summary="Record a payment on the current statement",
    description=(
        "Append a PAYMENT line to CURRENT statement. Positive `amount` is required. "
        "If `transaction_id` is provided, it must be SUCCESS and belong to the user."
    ),
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
        403: OpenApiResponse(description="Not allowed"),
        404: OpenApiResponse(description="Transaction not found"),
    },
)

close_current_schema = extend_schema(
    tags=["Credit · Management"],
    summary="Close the current statement",
    description=(
        "Close CURRENT statement and move it to PENDING_PAYMENT. "
        "Due date will be set based on active credit limit's grace days."
    ),
    responses={
        200: OpenApiResponse(
            response=CloseStatementResponseSerializer,
            description="Closed",
            examples=[OpenApiExample("OK", value={"success": True})],
        ),
        400: OpenApiResponse(description="No current statement"),
    },
)
