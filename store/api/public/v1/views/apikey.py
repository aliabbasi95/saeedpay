# store/api/public/v1/views/apikey.py

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from lib.cas_auth.views import PublicAPIView
from merchants.permissions import IsMerchant
from store.api.public.v1.serializers import (
    StoreApiKeyRegenerateRequestSerializer,
    StoreApiKeyRegenerateResponseSerializer,
)
from store.models import Store
from store.services.apikey import regenerate_store_api_key


@extend_schema(
    tags=["Store · API Key"],
    summary="تولید مجدد API Key فروشگاه",
    description="تنها مرچنت مالک فروشگاه می‌تواند کلید را بازتولید کند.",
    request=StoreApiKeyRegenerateRequestSerializer,
    responses={201: StoreApiKeyRegenerateResponseSerializer}
)
class StoreApiKeyRegenerateView(PublicAPIView):
    permission_classes = [IsAuthenticated, IsMerchant]
    serializer_class = StoreApiKeyRegenerateRequestSerializer

    def handle_post_request(self):
        serializer = self.get_serializer(
            data=self.request.data, context={"request": self.request}
        )
        serializer.is_valid(raise_exception=True)

        store_id = serializer.validated_data["store_id"]
        store = Store.objects.get(id=store_id)

        new_key = regenerate_store_api_key(store)
        self.response_data = StoreApiKeyRegenerateResponseSerializer(
            {"api_key": new_key}
        ).data
        self.response_status = status.HTTP_201_CREATED
        return self.response
