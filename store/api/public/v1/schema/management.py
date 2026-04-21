# store/api/public/v1/schema/management.py

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)

from store.api.public.v1.serializers import StoreCreateSerializer, StoreSerializer

STORE_MANAGEMENT_TAG = "Store · Management"

store_list_schema = extend_schema(
    operation_id="store_list",
    tags=[STORE_MANAGEMENT_TAG],
    summary="List merchant stores",
    description="Return all stores belonging to the authenticated merchant.",
    responses={
        200: OpenApiResponse(
            response=StoreSerializer(many=True),
            description="Store list returned successfully.",
        ),
        401: OpenApiResponse(
            description="Authentication credentials were not provided."
        ),
        403: OpenApiResponse(
            description="You do not have permission to perform this action."
        ),
    },
)

store_create_schema = extend_schema(
    operation_id="store_create",
    tags=[STORE_MANAGEMENT_TAG],
    summary="Create a store",
    description="Create a new store for the authenticated merchant.",
    request=StoreCreateSerializer,
    responses={
        201: OpenApiResponse(
            response=StoreSerializer,
            description="Store created successfully.",
        ),
        400: OpenApiResponse(description="Invalid input data."),
        401: OpenApiResponse(
            description="Authentication credentials were not provided."
        ),
        403: OpenApiResponse(
            description="You do not have permission to perform this action."
        ),
    },
    examples=[
        OpenApiExample(
            "CreateStoreRequest",
            summary="Create store request",
            value={
                "name": "فروشگاه نمونه",
                "address": "تهران، خیابان ولیعصر",
                "longitude": "51.3890",
                "latitude": "35.6892",
                "website_url": "https://example-store.com",
            },
            request_only=True,
        )
    ],
)

store_retrieve_schema = extend_schema(
    operation_id="store_retrieve",
    tags=[STORE_MANAGEMENT_TAG],
    summary="Retrieve a store",
    description="Return the details of a single store owned by the authenticated merchant.",
    responses={
        200: OpenApiResponse(
            response=StoreSerializer,
            description="Store retrieved successfully.",
        ),
        401: OpenApiResponse(
            description="Authentication credentials were not provided."
        ),
        403: OpenApiResponse(
            description="You do not have permission to perform this action."
        ),
        404: OpenApiResponse(description="Store not found."),
    },
)

store_update_put_schema = extend_schema(
    operation_id="store_update",
    tags=[STORE_MANAGEMENT_TAG],
    summary="Update a store",
    description=(
        "Fully update a store. "
        "If the store has already passed the editable stage, update is not allowed."
    ),
    request=StoreSerializer,
    parameters=[
        OpenApiParameter(
            name="id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description="Store ID.",
        )
    ],
    responses={
        200: OpenApiResponse(
            response=StoreSerializer,
            description="Store updated successfully.",
        ),
        400: OpenApiResponse(description="Invalid input data."),
        401: OpenApiResponse(
            description="Authentication credentials were not provided."
        ),
        403: OpenApiResponse(
            description="You do not have permission to perform this action or the store is not editable."
        ),
        404: OpenApiResponse(description="Store not found."),
    },
)

store_partial_update_schema = extend_schema(
    operation_id="store_partial_update",
    tags=[STORE_MANAGEMENT_TAG],
    summary="Partially update a store",
    description=(
        "Partially update a store. "
        "If the store has already passed the editable stage, update is not allowed."
    ),
    request=StoreSerializer,
    parameters=[
        OpenApiParameter(
            name="id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description="Store ID.",
        )
    ],
    responses={
        200: OpenApiResponse(
            response=StoreSerializer,
            description="Store updated successfully.",
        ),
        400: OpenApiResponse(description="Invalid input data."),
        401: OpenApiResponse(
            description="Authentication credentials were not provided."
        ),
        403: OpenApiResponse(
            description="You do not have permission to perform this action or the store is not editable."
        ),
        404: OpenApiResponse(description="Store not found."),
    },
)

store_delete_schema = extend_schema(
    operation_id="store_delete",
    tags=[STORE_MANAGEMENT_TAG],
    summary="Delete a store",
    description="Delete a store owned by the authenticated merchant.",
    responses={
        204: OpenApiResponse(description="Store deleted successfully."),
        401: OpenApiResponse(
            description="Authentication credentials were not provided."
        ),
        403: OpenApiResponse(
            description="You do not have permission to perform this action."
        ),
        404: OpenApiResponse(description="Store not found."),
    },
)
