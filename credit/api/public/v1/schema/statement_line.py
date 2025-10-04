# credit/api/public/v1/schema/statement_line.py

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    extend_schema, extend_schema_view,
    OpenApiParameter, OpenApiResponse, OpenApiExample,
)

from credit.api.public.v1.serializers.credit import StatementLineSerializer

statement_line_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=["Credit · Statement Lines"],
        summary="List user's statement lines",
        description="Optionally filter by `?statement_id=`. Results are ordered by `-created_at`.",
        parameters=[
            OpenApiParameter(
                name="statement_id",
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.INT,
                description="Filter by a specific statement id",
                examples=[
                    OpenApiExample("Filter by statement #42", value=42),
                ],
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=StatementLineSerializer(many=True),
                description="Paginated statement lines",
                examples=[
                    OpenApiExample(
                        "Sample page",
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
        tags=["Credit · Statement Lines"],
        summary="Retrieve a statement line",
        responses={200: StatementLineSerializer},
    ),
)
