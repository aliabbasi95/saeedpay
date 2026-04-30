# apps/store/api/public/v1/schema/apikey.py

from drf_spectacular.utils import OpenApiResponse, extend_schema

from apps.store.api.public.v1.serializers import StoreApiKeyRegenerateResponseSerializer

STORE_API_KEY_TAG = "Store · API Keys"

store_regenerate_api_key_schema = extend_schema(
    tags=[STORE_API_KEY_TAG],
    summary="Regenerate store API key",
    description="Only the merchant owner of the store can regenerate its API key.",
    responses={
        201: OpenApiResponse(
            response=StoreApiKeyRegenerateResponseSerializer,
            description="API key regenerated successfully.",
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
