# credit/api/public/v1/schema/statement_line.py

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from credit.api.public.v1.serializers.credit import StatementLineSerializer

STATEMENT_LINES_TAG = "Credit · Statement Lines"

statement_line_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=[STATEMENT_LINES_TAG],
        summary="List user's statement lines",
        description=(
            "Return the authenticated user's statement lines. "
            "Optionally filter by statement ID."
        ),
        parameters=[
            OpenApiParameter(
                name="statement_id",
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.INT,
                description="Filter by statement ID.",
                examples=[OpenApiExample("FilterByStatement", value=42)],
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=StatementLineSerializer(many=True),
                description="Paginated statement lines.",
                examples=[
                    OpenApiExample(
                        "SamplePage",
                        value={
                            "count": 2,
                            "next": None,
                            "previous": None,
                            "results": [
                                {
                                    "id": 10,
                                    "statement": 42,
                                    "type": "purchase",
                                    "amount": 150000,
                                    "transaction": 311,
                                    "description": "Store purchase",
                                    "is_voided": False,
                                    "voided_at": None,
                                    "void_reason": None,
                                    "reverses": None,
                                    "created_at": "2025-01-01T10:00:00Z",
                                }
                            ],
                        },
                    )
                ],
            ),
        },
    ),
    retrieve=extend_schema(
        tags=[STATEMENT_LINES_TAG],
        summary="Retrieve a statement line",
        description="Return a single statement line belonging to the authenticated user.",
        responses={200: StatementLineSerializer},
    ),
)
