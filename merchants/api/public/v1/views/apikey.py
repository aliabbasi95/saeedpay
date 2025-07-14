# merchants/api/public/v1/views/apikey.py
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from lib.cas_auth.views import PublicAPIView
from merchants.api.public.v1.serializers import \
    MerchantApiKeyRegenerateResponseSerializer
from merchants.permissions import IsMerchant
from merchants.services import regenerate_merchant_api_key


class MerchantApiKeyRegenerateView(PublicAPIView):
    permission_classes = [IsAuthenticated, IsMerchant]
    serializer_class = MerchantApiKeyRegenerateResponseSerializer

    def handle_post_request(self):
        merchant = self.request.user.merchant
        new_key = regenerate_merchant_api_key(merchant)
        self.response_data = self.serializer_class({"api_key": new_key}).data
        self.response_status = status.HTTP_201_CREATED
        return self.response
