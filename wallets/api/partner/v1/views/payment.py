# wallets/api/partner/v1/views/payment.py

import logging

from django.conf import settings
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from merchants.permissions import IsMerchant
from profiles.models import Profile
from saeedpay.logging import log_event
from store.authentication import StoreApiKeyAuthentication
from wallets.api.partner.v1.schema.payment import (
    partner_payment_request_viewset_schema,
    partner_payment_verify_schema,
)
from wallets.api.partner.v1.serializers import (
    PaymentActionResponseSerializer,
    PaymentRequestCreateResponseSerializer,
    PaymentRequestCreateSerializer,
    PaymentRequestPartnerDetailSerializer,
)
from wallets.api.payment_responses import (
    build_payment_response_payload,
    payment_error_response,
    payment_internal_error_response,
    payment_success_response,
)
from wallets.models import PaymentRequest
from wallets.services.payment import (
    check_and_expire_payment_request,
    create_payment_request,
    verify_payment_request,
)
from wallets.utils.choices import PaymentFlowType
from wallets.utils.consts import FRONTEND_PAYMENT_DETAIL_URL

logger = logging.getLogger("saeedpay.wallets.payment")


def _extract_validation_code(exc, default="validation_error"):
    if hasattr(exc, "get_codes"):
        codes = exc.get_codes()
        if isinstance(codes, list) and codes:
            return codes[0]
        if isinstance(codes, str):
            return codes
        if isinstance(codes, dict):
            first_value = next(iter(codes.values()), default)
            if isinstance(first_value, list) and first_value:
                return first_value[0]
            if isinstance(first_value, str):
                return first_value
    return getattr(exc, "code", default)


@partner_payment_request_viewset_schema
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

    def _log_unexpected_error(
        self,
        *,
        action: str,
        exc: Exception,
        payment_request=None,
    ):
        log_event(
            logger,
            level="error",
            event="partner_payment_api_unexpected_error",
            message="Unexpected error in partner payment API.",
            module="wallets.payment",
            action=action,
            payment_request_id=getattr(payment_request, "id", None),
            payment_request_reference=getattr(
                payment_request,
                "reference_code",
                None,
            ),
            store_id=getattr(payment_request, "store_id", None)
            or getattr(getattr(self.request, "store", None), "id", None),
            error=str(exc),
        )

    def get_queryset(self):
        return PaymentRequest.objects.select_related(
            "store", "paid_by", "paid_wallet"
        ).filter(store=self.request.store)

    def create(self, request, *args, **kwargs):
        serializer = PaymentRequestCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data["flow_type"] != PaymentFlowType.ONLINE:
            return payment_error_response(
                detail="ایجاد درخواست QR POS از این API مجاز نیست.",
                code="unsupported_flow_type",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            profile = Profile.objects.select_related("user").get(
                national_id=data["national_id"]
            )
            customer = profile.user.customer
        except Profile.DoesNotExist:
            return payment_error_response(
                detail="مشتری با این کد ملی یافت نشد.",
                code="customer_not_found",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as exc:
            self._log_unexpected_error(
                action="partner_create_customer_lookup",
                exc=exc,
            )
            return payment_error_response(
                detail="مشتری با این کد ملی یافت نشد.",
                code="customer_not_found",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        payment_request = create_payment_request(
            store=request.store,
            customer=customer,
            amount=data["amount"],
            return_url=data["return_url"],
            description=data.get("description", ""),
            external_guid=data.get("external_guid"),
            flow_type=PaymentFlowType.ONLINE,
        )

        payment_url = (
            f"{settings.FRONTEND_BASE_URL}"
            f"{FRONTEND_PAYMENT_DETAIL_URL}"
            f"{payment_request.reference_code}/"
        )

        payload = build_payment_response_payload(
            detail="درخواست پرداخت با موفقیت ایجاد شد.",
            code="payment_request_created",
            payment_request=payment_request,
            extra={
                "payment_request_id": payment_request.id,
                "flow_type": payment_request.flow_type,
                "payment_url": payment_url,
            },
        )

        serializer = PaymentRequestCreateResponseSerializer(payload)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        payment_request = self.get_object()
        check_and_expire_payment_request(payment_request, raise_exception=False)
        payment_request.refresh_from_db()

        serializer = PaymentRequestPartnerDetailSerializer(payment_request)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @partner_payment_verify_schema
    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, *args, **kwargs):
        reference_code = kwargs.get(self.lookup_field)
        try:
            payment_request = self.get_queryset().get(reference_code=reference_code)
        except PaymentRequest.DoesNotExist:
            return payment_error_response(
                detail="درخواست پرداخت پیدا نشد.",
                code="payment_request_not_found",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        try:
            payment = verify_payment_request(
                payment_request,
                store=request.store,
            )
            payment_request.refresh_from_db()
            payment.refresh_from_db()
        except ValidationError as exc:
            return payment_error_response(
                detail=str(exc),
                code=_extract_validation_code(exc),
                http_status=status.HTTP_400_BAD_REQUEST,
                payment_request=payment_request,
            )
        except Exception as exc:
            self._log_unexpected_error(
                action="partner_verify",
                exc=exc,
                payment_request=payment_request,
            )
            return payment_internal_error_response(
                payment_request=payment_request,
            )

        payload_response = payment_success_response(
            detail="پرداخت نهایی شد.",
            code="payment_verified",
            payment_request=payment_request,
            payment=payment,
            http_status=status.HTTP_200_OK,
        )

        serializer = PaymentActionResponseSerializer(payload_response.data)
        return Response(serializer.data, status=payload_response.status_code)
