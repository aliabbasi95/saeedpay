from rest_framework import status

from lib.cas_auth.views import PublicAPIView
from wallets.models import PaymentRequest, Wallet
from wallets.services import pay_payment_request
from wallets.api.public.v1.serializers import PaymentConfirmSerializer

class PaymentConfirmView(PublicAPIView):
    serializer_class = PaymentConfirmSerializer

    def perform_save(self, serializer):
        request_id = serializer.validated_data["payment_request_id"]
        wallet_id = serializer.validated_data["wallet_id"]

        payment_request = PaymentRequest.objects.get(id=request_id, is_paid=False)
        wallet = Wallet.objects.get(id=wallet_id, user=self.request.user)
        pay_payment_request(payment_request, self.request.user, wallet)
        self.response_data = {"detail": "پرداخت با موفقیت انجام شد."}
        self.response_status = status.HTTP_200_OK
