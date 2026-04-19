# tickets/api/public/v1/schema/category.py

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

TICKETS_TAG = "Tickets"

ticket_category_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=[TICKETS_TAG],
        summary="List ticket categories",
        description="Return all available ticket categories.",
        responses={
            200: OpenApiResponse(
                description="Ticket categories returned successfully.",
                examples=[
                    OpenApiExample(
                        "CategoryListResponse",
                        value=[
                            {
                                "id": 1,
                                "name": "Technical",
                                "description": "Technical support requests",
                            },
                            {
                                "id": 2,
                                "name": "Billing",
                                "description": "Payment and invoice issues",
                            },
                        ],
                        response_only=True,
                    )
                ],
            )
        },
    ),
    retrieve=extend_schema(
        tags=[TICKETS_TAG],
        summary="Retrieve a ticket category",
        description="Return the details of a single ticket category.",
        responses={
            200: OpenApiResponse(
                description="Ticket category retrieved successfully.",
                examples=[
                    OpenApiExample(
                        "CategoryRetrieveResponse",
                        value={
                            "id": 1,
                            "name": "Technical",
                            "description": "Technical support requests",
                            "icon": "/media/tickets/icons/technical.svg",
                            "color": "#2563eb",
                        },
                        response_only=True,
                    )
                ],
            ),
            404: OpenApiResponse(description="Ticket category not found."),
        },
    ),
)
