# wallets/api/partner/v1/views/installment_request.py
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.serializers import Serializer

from lib.cas_auth.views import PublicAPIView, PublicGetAPIView
from merchants.authentication import MerchantAPIKeyAuthentication
from merchants.permissions import IsMerchant
from wallets.api.partner.v1.serializers import (
    InstallmentRequestDetailSerializer,
    InstallmentRequestCreateSerializer,
)
from wallets.models import InstallmentRequest
from wallets.services.credit import evaluate_user_credit
from wallets.utils.choices import InstallmentRequestStatus
from wallets.utils.consts import FRONTEND_INSTALLMENT_REQUEST_DETAIL_URL


class InstallmentRequestCreateView(PublicAPIView):
    authentication_classes = [MerchantAPIKeyAuthentication]
    permission_classes = [IsMerchant]
    serializer_class = InstallmentRequestCreateSerializer

    def perform_save(self, serializer):
        data = serializer.validated_data
        credit_limit_amount = evaluate_user_credit(
            data["amount"], data["contract"]
        )
        req = InstallmentRequest.objects.create(
            merchant=self.request.user.merchant,
            customer=data["customer"],
            national_id=data["national_id"],
            proposal_amount=data["amount"],
            return_url=data["return_url"],
            credit_limit_amount=credit_limit_amount,
            contract=data["contract"],
        )
        payment_url = f"{settings.FRONTEND_BASE_URL}{FRONTEND_INSTALLMENT_REQUEST_DETAIL_URL}{req.reference_code}/"

        self.response_data = {
            "installment_request_id": req.id,
            "reference_code": req.reference_code,
            "proposal_amount": req.proposal_amount,
            "credit_limit_amount": req.credit_limit_amount,
            "payment_url": payment_url,
            "return_url": req.return_url,
            "status": req.status,
        }
        self.response_status = status.HTTP_201_CREATED


class InstallmentRequestRetrieveView(PublicGetAPIView):
    authentication_classes = [MerchantAPIKeyAuthentication]
    permission_classes = [IsMerchant]
    serializer_class = InstallmentRequestDetailSerializer

    def get(self, request, reference_code):
        qs = InstallmentRequest.objects.filter(
            reference_code=reference_code,
            merchant=request.user.merchant
        )
        obj = qs.first()

        if not obj:
            self.response_data = {"detail": "درخواست اقساطی یافت نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response

        self.response_data = self.get_serializer(obj).data
        self.response_status = status.HTTP_200_OK
        return self.response


class InstallmentRequestVerifyView(PublicAPIView):
    serializer_class = Serializer
    authentication_classes = [MerchantAPIKeyAuthentication]
    permission_classes = [IsMerchant]

    def post(self, request, reference_code):
        req = InstallmentRequest.objects.filter(
            reference_code=reference_code
        ).first()
        if not req:
            self.response_data = {"detail": "درخواست اقساطی یافت نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response

        if req.status != InstallmentRequestStatus.AWAITING_MERCHANT_CONFIRMATION:
            self.response_data = {
                "detail": "درخواست هنوز توسط کاربر تایید نشده است."
            }
            self.response_status = status.HTTP_400_BAD_REQUEST
            return self.response

        req.status = InstallmentRequestStatus.COMPLETED
        req.merchant_confirmed_at = timezone.now()
        req.save()

        self.response_data = {
            "detail": "درخواست با موفقیت نهایی شد.",
            "reference_code": req.reference_code,
            "confirmed_amount": req.confirmed_amount,
            "duration_months": req.duration_months,
            "period_months": req.period_months,
        }
        self.response_status = status.HTTP_200_OK
        return self.response
