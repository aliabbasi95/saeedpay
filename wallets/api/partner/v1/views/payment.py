# wallets/api/partner/v1/views/payment.py

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

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
    viewsets.GenericViewSet,
):
    """
    create:   POST /payment-requests/               -> create payment request
    retrieve: GET  /payment-requests/{ref}/         -> partner-side details
    verify:   POST /payment-requests/{ref}/verify/  -> finalize payment
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
        return (
            PaymentRequest.objects
            .select_related("store", "paid_by", "paid_wallet")
            .filter(store=self.request.store)
        )

    @extend_schema(
        summary="ایجاد درخواست پرداخت",
        request=PaymentRequestCreateSerializer,
        responses={201: PaymentRequestCreateResponseSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = PaymentRequestCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            profile = Profile.objects.get(national_id=data["national_id"])
            customer = profile.user.customer
        except Exception:
            return Response(
                {"detail": "مشتری با این کد ملی یافت نشد."},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment_request = create_payment_request(
            store=request.store,
            customer=customer,
            amount=data["amount"],
            return_url=data["return_url"],
            description=data.get("description", ""),
            external_guid=data.get("external_guid"),
        )

        payment_url = (
            f"{settings.FRONTEND_BASE_URL}"
            f"{FRONTEND_PAYMENT_DETAIL_URL}"
            f"{payment_request.reference_code}/"
        )

        payload = {
            "payment_request_id": payment_request.id,
            "payment_reference_code": payment_request.reference_code,
            "amount": payment_request.amount,
            "description": payment_request.description,
            "return_url": payment_request.return_url,
            "status": payment_request.status,
            "payment_url": payment_url,
        }
        return Response(
            PaymentRequestCreateResponseSerializer(payload).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="جزییات درخواست پرداخت",
        responses={200: PaymentRequestPartnerDetailSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        payment_request = self.get_object()

        if payment_request.expires_at and payment_request.status not in (
                PaymentRequestStatus.EXPIRED,
                PaymentRequestStatus.CANCELLED,
                PaymentRequestStatus.COMPLETED,
        ):
            if payment_request.expires_at < timezone.localtime(timezone.now()):
                payment_request.mark_expired()

        serializer = PaymentRequestPartnerDetailSerializer(payment_request)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="تایید نهایی پرداخت",
        description="پس از پرداخت موفق توسط مشتری، فروشگاه پرداخت را نهایی می‌کند.",
        responses={
            200: PaymentVerifyResponseSerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Payment request not found"),
        },
    )
    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, *args, **kwargs):
        reference_code = kwargs.get(self.lookup_field)
        try:
            payment_request = self.get_queryset().get(
                reference_code=reference_code
            )
        except PaymentRequest.DoesNotExist:
            return Response(
                {"detail": "درخواست پرداخت پیدا نشد."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            payment = verify_payment_request(
                payment_request,
                store=request.store,
            )
        except ValidationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = {
            "detail": "پرداخت نهایی شد.",
            "payment_reference_code": payment_request.reference_code,
            "transaction_reference_code": (
                    getattr(payment, "operation_reference_code", "") or ""
            ),
            "amount": payment_request.amount,
        }
        return Response(
            PaymentVerifyResponseSerializer(payload).data,
            status=status.HTTP_200_OK,
        )
