# wallets/api/partner/v1/views/payment.py

# wallets/api/partner/v1/views/payment.py

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import (
    extend_schema, OpenApiResponse,
)
from rest_framework import status, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from merchants.permissions import IsMerchant
from profiles.models import Profile
from store.authentication import StoreApiKeyAuthentication
from wallets.api.partner.v1.serializers import (
    PaymentRequestCreateSerializer,
    PaymentRequestCreateResponseSerializer,
    PaymentVerifyResponseSerializer,
    PaymentRequestPartnerDetailSerializer,
)
from wallets.models import PaymentRequest
from wallets.services.payment import (
    create_payment_request,
    verify_payment_request,
)
from wallets.utils.choices import PaymentRequestStatus
from wallets.utils.consts import FRONTEND_PAYMENT_DETAIL_URL


@extend_schema(tags=["Wallet · Payment Requests (Partner)"])
class PartnerPaymentRequestViewSet(
    ScopedThrottleByActionMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    """
    create:   POST /payment-requests/           → create payment request (by store)
    retrieve: GET  /payment-requests/{ref}/     → partner-side details
    verify:   POST /payment-requests/{ref}/verify/ → finalize payment after success callback
    """
    authentication_classes = [StoreApiKeyAuthentication]
    permission_classes = [IsMerchant]
    serializer_class = PaymentRequestPartnerDetailSerializer
    lookup_field = "reference_code"
    lookup_value_regex = r"[-A-Za-z0-9_]+"

    throttle_scope_map = {
        "default": "partner-payment-read",
        "create": "partner-payment-write",
        "retrieve": "partner-payment-read",
        "verify": "partner-payment-write",
    }

    def get_queryset(self):
        # Scope to the authenticated store (from API Key)
        return (
            PaymentRequest.objects
            .select_related("store", "paid_by", "paid_wallet")
            .filter(store=self.request.store)
        )

    # ---------- create ----------
    @extend_schema(
        summary="ایجاد درخواست پرداخت",
        request=PaymentRequestCreateSerializer,
        responses={201: PaymentRequestCreateResponseSerializer},
    )
    def create(self, request, *args, **kwargs):
        ser = PaymentRequestCreateSerializer(
            data=request.data, context={"request": request}
        )
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        # Resolve customer by national_id
        try:
            profile = Profile.objects.get(national_id=data["national_id"])
            customer = profile.user.customer
        except Exception:
            return Response(
                {"detail": "مشتری با این کد ملی یافت نشد."},
                status=status.HTTP_404_NOT_FOUND
            )

        req = create_payment_request(
            store=request.store,
            customer=customer,
            amount=data["amount"],
            return_url=data.get("return_url"),
            description=data.get("description", ""),
            external_guid=data.get("external_guid"),
        )
        payment_url = f"{settings.FRONTEND_BASE_URL}{FRONTEND_PAYMENT_DETAIL_URL}{req.reference_code}/"
        payload = {
            "payment_request_id": req.id,
            "payment_reference_code": req.reference_code,
            "amount": req.amount,
            "description": req.description,
            "return_url": req.return_url,
            "status": req.status,
            "payment_url": payment_url,
        }
        out = PaymentRequestCreateResponseSerializer(payload).data
        return Response(out, status=status.HTTP_201_CREATED)

    # ---------- retrieve ----------
    @extend_schema(
        summary="جزییات درخواست پرداخت (سمت فروشگاه)",
        responses={200: PaymentRequestPartnerDetailSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        # Mark expired if needed
        if obj.expires_at and obj.status not in (
                PaymentRequestStatus.EXPIRED, PaymentRequestStatus.CANCELLED,
                PaymentRequestStatus.COMPLETED
        ):
            if obj.expires_at < timezone.localtime(timezone.now()):
                obj.mark_expired()
        ser = PaymentRequestPartnerDetailSerializer(obj)
        return Response(ser.data, status=status.HTTP_200_OK)

    # ---------- verify ----------
    @extend_schema(
        summary="تایید نهایی پرداخت",
        description="پس از پرداخت موفق توسط مشتری، فروشگاه با این API پرداخت را تایید نهایی می‌کند",
        responses={
            200: PaymentVerifyResponseSerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Payment request not found"),
        },
    )
    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, *args, **kwargs):
        ref = kwargs.get(self.lookup_field)
        try:
            pr = self.get_queryset().get(reference_code=ref)
        except PaymentRequest.DoesNotExist:
            return Response(
                {"detail": "درخواست پرداخت پیدا نشد."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            txn = verify_payment_request(pr)
        except Exception as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

        payload = {
            "detail": "پرداخت نهایی شد.",
            "payment_reference_code": pr.reference_code,
            "transaction_reference_code": txn.reference_code,
            "amount": pr.amount,
        }
        return Response(
            PaymentVerifyResponseSerializer(payload).data,
            status=status.HTTP_200_OK
        )
