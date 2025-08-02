# wallets/api/internal/v1/views/installment_request.py
from django.conf import settings
from django.utils import timezone
from rest_framework import status

from lib.cas_auth.views import PublicAPIView, PublicGetAPIView
from merchants.authentication import MerchantAPIKeyAuthentication
from merchants.permissions import IsMerchant
from wallets.api.public.v1.serializers import (
    InstallmentRequestCreateSerializer,
    InstallmentRequestDetailSerializer,
    InstallmentRequestConfirmSerializer,
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


class InstallmentRequestDetailView(PublicGetAPIView):
    serializer_class = InstallmentRequestDetailSerializer

    def get(self, request, reference_code):
        obj = InstallmentRequest.objects.filter(
            reference_code=reference_code
        ).first()
        if not obj:
            self.response_data = {"detail": "درخواست اقساطی یافت نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response

        self.response_data = self.get_serializer(obj).data
        self.response_status = status.HTTP_200_OK
        return self.response


class InstallmentCalculationView(PublicAPIView):
    serializer_class = InstallmentRequestConfirmSerializer

    def post(self, request, reference_code):
        obj = InstallmentRequest.objects.filter(
            reference_code=reference_code,
            merchants=request.user.merchant
        ).first()
        if not obj:
            self.response_data = {"detail": "درخواست اقساطی یافت نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response
        serializer = self.get_serializer(
            data=request.data,
            context={"installment_request": obj}
        )
        serializer.is_valid(raise_exception=True)

        self.response_data = serializer.validated_data["installment_plan"]
        self.response_status = status.HTTP_200_OK
        return self.response


class InstallmentRequestConfirmView(PublicAPIView):
    serializer_class = InstallmentRequestConfirmSerializer

    def post(self, request, reference_code):
        obj = InstallmentRequest.objects.filter(
            reference_code=reference_code,
            merchant=request.user.merchant
        ).first()
        if not obj:
            self.response_data = {"detail": "درخواست اقساطی یافت نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response

        serializer = self.get_serializer(
            data=request.data,
            context={"installment_request": obj}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        obj.confirmed_amount = data["confirmed_amount"]
        obj.duration_months = data["duration_months"]
        obj.period_months = data["period_months"]
        obj.status = InstallmentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        obj.user_confirmed_at = timezone.now()
        obj.save()

        self.response_data = {
            "detail": "درخواست اقساطی با موفقیت تایید شد.",
            **data["installment_plan"]
        }
        self.response_status = status.HTTP_200_OK
        return self.response
