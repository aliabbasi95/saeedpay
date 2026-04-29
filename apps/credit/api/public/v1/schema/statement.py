# credit/api/public/v1/schema/statement.py

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)

from credit.api.public.v1.serializers.credit import (
    CloseStatementResponseSerializer,
    StatementDetailSerializer,
    StatementListSerializer,
)

STATEMENTS_TAG = "Credit · Statements"
TRANSACTIONS_TAG = "Credit · Transactions"
MANAGEMENT_TAG = "Credit · Management"

statement_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=[STATEMENTS_TAG],
        summary="List user's statements",
        description="Return a paginated list of the authenticated user's statements.",
        parameters=[
            OpenApiParameter(
                name="ordering",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                required=False,
                description="Optional ordering. Default is most recent first.",
                examples=[
                    OpenApiExample(
                        "DefaultOrdering",
                        value="-year,-month,-created_at",
                    )
                ],
            ),
        ],
        responses={200: StatementListSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=[STATEMENTS_TAG],
        summary="Retrieve a statement",
        description="Return a single statement with its lines.",
        responses={200: StatementDetailSerializer},
    ),
)

add_purchase_schema = extend_schema(
    tags=[TRANSACTIONS_TAG],
    summary="Record a purchase from a successful transaction",
    description=(
        "Append a PURCHASE line to the current statement for the authenticated user."
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
            description="Purchase recorded successfully.",
            examples=[OpenApiExample("Success", value={"success": True})],
        ),
        400: OpenApiResponse(description="Validation or business rule error."),
        403: OpenApiResponse(description="Transaction does not belong to the user."),
        404: OpenApiResponse(description="Transaction not found."),
    },
)

add_payment_schema = extend_schema(
    tags=[TRANSACTIONS_TAG],
    summary="Record a payment on the current statement",
    description="Append a PAYMENT line to the current statement.",
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
            description="Payment recorded successfully.",
            examples=[OpenApiExample("Success", value={"success": True})],
        ),
        400: OpenApiResponse(description="Validation or business rule error."),
        403: OpenApiResponse(description="Transaction does not belong to the user."),
        404: OpenApiResponse(description="Transaction not found."),
    },
)

close_current_schema = extend_schema(
    tags=[MANAGEMENT_TAG],
    summary="Close the current statement",
    description="Close the current statement and move it to pending payment status.",
    responses={
        200: OpenApiResponse(
            response=CloseStatementResponseSerializer,
            description="Statement closed successfully.",
            examples=[OpenApiExample("Success", value={"success": True})],
        ),
        400: OpenApiResponse(description="No current statement or close failed."),
    },
)
