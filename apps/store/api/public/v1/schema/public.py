# store/api/public/v1/schema/public.py

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)

from store.api.public.v1.serializers import PublicStoreSerializer

STORE_PUBLIC_TAG = "Store · Public"

public_store_list_schema = extend_schema(
    operation_id="public_store_list",
    tags=[STORE_PUBLIC_TAG],
    summary="List public stores",
    description=(
        "Return approved and active stores for public access. "
        "The response is paginated."
    ),
    parameters=[
        OpenApiParameter(
            name="page",
            type=int,
            location=OpenApiParameter.QUERY,
            description="Page number.",
            required=False,
        ),
        OpenApiParameter(
            name="page_size",
            type=int,
            location=OpenApiParameter.QUERY,
            description="Number of items per page.",
            required=False,
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=PublicStoreSerializer(many=True),
            description="Public store list returned successfully.",
            examples=[
                OpenApiExample(
                    "PaginatedResponse",
                    summary="Paginated public stores",
                    value={
                        "count": 150,
                        "next": "http://example.com/api/v1/public-stores/?page=2",
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "name": "فروشگاه نمونه",
                                "address": "تهران، خیابان ولیعصر",
                                "longitude": "51.3890",
                                "latitude": "35.6892",
                                "website_url": "https://example-store.com",
                                "status": "active",
                                "status_display": "فعال",
                                "logo": "http://example.com/media/store_logos/store_1_abc123.jpg",
                                "rating": 82.5,
                            }
                        ],
                    },
                    response_only=True,
                )
            ],
        )
    },
)

public_store_retrieve_schema = extend_schema(
    operation_id="public_store_retrieve",
    tags=[STORE_PUBLIC_TAG],
    summary="Retrieve a public store",
    description="Return the details of a single approved and active public store.",
    responses={
        200: OpenApiResponse(
            response=PublicStoreSerializer,
            description="Public store retrieved successfully.",
        ),
        404: OpenApiResponse(description="Store not found or inactive."),
    },
)
