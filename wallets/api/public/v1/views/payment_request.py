# wallets/api/internal/v1/views/payment_request.py
from rest_framework import status

from lib.cas_auth.views import PublicAPIView
from merchants.authentication import MerchantAPIKeyAuthentication
from merchants.permissions import IsMerchant
from wallets.api.public.v1.serializers import PaymentRequestCreateSerializer
from wallets.services.payment import create_payment_request


class PaymentRequestCreateView(PublicAPIView):
    authentication_classes = [MerchantAPIKeyAuthentication]
    permission_classes = [IsMerchant]
    serializer_class = PaymentRequestCreateSerializer

    def perform_save(self, serializer):
        merchant = self.request.user
        req = create_payment_request(
            merchant=merchant,
            amount=serializer.validated_data["amount"],
            description=serializer.validated_data.get("description", ""),
            callback_url=serializer.validated_data.get("callback_url"),
        )
        self.response_data = {
            "payment_request_id": req.id,
            "uuid": req.guid,
            "amount": req.amount,
            "description": req.description,
            "callback_url": req.callback_url,
        }
        self.response_status = status.HTTP_201_CREATED
