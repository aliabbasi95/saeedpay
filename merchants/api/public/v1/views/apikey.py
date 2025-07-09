# merchants/api/public/v1/views/apikey.py
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from lib.cas_auth.views import PublicAPIView
from merchants.permissions import IsMerchant
from merchants.services import regenerate_merchant_api_key


class MerchantApiKeyRegenerateView(PublicAPIView):
    permission_classes = [IsAuthenticated, IsMerchant]

    def post(self, request):
        merchant = request.user.merchant
        new_key = regenerate_merchant_api_key(merchant)
        return Response({"api_key": new_key}, status=status.HTTP_201_CREATED)
