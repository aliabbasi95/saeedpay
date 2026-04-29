# wallets/api/public/v1/views/payment.py

import logging

from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotAuthenticated, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from saeedpay.logging import log_event
from wallets.api.payment_responses import (
    payment_error_response,
    payment_internal_error_response,
    payment_success_response,
)
from wallets.api.public.v1.schema import (
    payment_confirm_schema,
    payment_request_viewset_schema,
)
from wallets.api.public.v1.serializers.payment import (
    PaymentActionResponseSerializer,
    PaymentConfirmSerializer,
    PaymentRequestDetailWithWalletsSerializer,
    PaymentRequestListItemSerializer,
)
from wallets.models import PaymentRequest, Wallet
from wallets.services.payment import (
    check_and_expire_payment_request,
    pay_payment_request,
)
from wallets.services.payment.payment_request_service import (
    validate_payment_request_payer_access,
)
from wallets.utils.choices import OwnerType

logger = logging.getLogger("saeedpay.wallets.payment")

_ALLOWED_ORDERING = {"created_at", "-created_at", "amount", "-amount"}


def _parse_dt_maybe(value):
    if not value:
        return None

    dt = parse_datetime(value)
    if dt:
        return dt

    return parse_date(value)


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


@payment_request_viewset_schema
class PaymentRequestViewSet(
    ScopedThrottleByActionMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [AllowAny]
    lookup_field = "reference_code"
    lookup_value_regex = r"[-A-Za-z0-9_]+"
    throttle_scope_map = {
        "default": "user",
        "confirm": "payment-confirm",
        "retrieve": "user",
        "list": "user",
    }

    def _require_authenticated_user(self, request):
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated("احراز هویت الزامی است.")

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
            event="payment_api_unexpected_error",
            message="Unexpected error in public payment API.",
            module="wallets.payment",
            action=action,
            payment_request_id=getattr(payment_request, "id", None),
            payment_request_reference=getattr(
                payment_request,
                "reference_code",
                None,
            ),
            store_id=getattr(payment_request, "store_id", None),
            error=str(exc),
        )

    def get_queryset(self):
        if self.action in {"retrieve", "confirm"}:
            return PaymentRequest.objects.select_related("store").only(
                "reference_code",
                "amount",
                "description",
                "status",
                "flow_type",
                "expires_at",
                "created_at",
                "store_id",
                "store__id",
                "store__name",
                "customer_id",
                "return_url",
                "paid_at",
            )

        user = self.request.user
        customer = getattr(user, "customer", None)
        if not customer:
            return PaymentRequest.objects.none()

        params = self.request.query_params
        qs = (
            PaymentRequest.objects.select_related("store")
            .only(
                "reference_code",
                "amount",
                "description",
                "status",
                "flow_type",
                "expires_at",
                "created_at",
                "store_id",
                "store__id",
                "store__name",
                "customer_id",
                "return_url",
                "paid_at",
            )
            .filter(customer=customer)
        )

        status_param = params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        store_id = params.get("store_id")
        if store_id:
            qs = qs.filter(store_id=store_id)

        q = params.get("q")
        if q:
            qs = qs.filter(reference_code__icontains=q)

        created_from = _parse_dt_maybe(params.get("created_from"))
        if created_from:
            qs = qs.filter(created_at__gte=created_from)

        created_to = _parse_dt_maybe(params.get("created_to"))
        if created_to:
            qs = qs.filter(created_at__lte=created_to)

        expires_from = _parse_dt_maybe(params.get("expires_from"))
        if expires_from:
            qs = qs.filter(expires_at__gte=expires_from)

        expires_to = _parse_dt_maybe(params.get("expires_to"))
        if expires_to:
            qs = qs.filter(expires_at__lte=expires_to)

        ordering = params.get("ordering") or "-created_at"
        if ordering not in _ALLOWED_ORDERING:
            ordering = "-created_at"

        return qs.order_by(ordering)

    def list(self, request, *args, **kwargs):
        self._require_authenticated_user(request)
        self.serializer_class = PaymentRequestListItemSerializer
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        self.serializer_class = PaymentRequestDetailWithWalletsSerializer
        payment_request = self.get_object()
        check_and_expire_payment_request(payment_request, raise_exception=False)
        payment_request.refresh_from_db()

        serializer = self.get_serializer(
            payment_request,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @payment_confirm_schema
    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, *args, **kwargs):
        self._require_authenticated_user(request)
        payment_request = self.get_object()

        try:
            check_and_expire_payment_request(payment_request)
            payment_request.refresh_from_db()
            validate_payment_request_payer_access(
                payment_request=payment_request,
                user=request.user,
            )
        except ValidationError as exc:
            code = _extract_validation_code(exc)
            http_status = (
                status.HTTP_410_GONE
                if code == "expired"
                else status.HTTP_400_BAD_REQUEST
            )
            return payment_error_response(
                detail=str(exc),
                code=code,
                http_status=http_status,
                payment_request=payment_request,
            )
        except Exception as exc:
            self._log_unexpected_error(
                action="confirm_precheck",
                exc=exc,
                payment_request=payment_request,
            )
            return payment_internal_error_response(
                payment_request=payment_request,
            )

        serializer = PaymentConfirmSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        wallet_id = serializer.validated_data["wallet_id"]
        try:
            wallet = Wallet.objects.get(
                id=wallet_id,
                user=request.user,
                owner_type=OwnerType.CUSTOMER,
            )
        except Wallet.DoesNotExist:
            return payment_error_response(
                detail="کیف پول پیدا نشد یا متعلق به شما نیست.",
                code="wallet_not_owned",
                http_status=status.HTTP_400_BAD_REQUEST,
                payment_request=payment_request,
            )

        try:
            payment = pay_payment_request(payment_request, request.user, wallet)
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
                action="confirm_pay_payment_request",
                exc=exc,
                payment_request=payment_request,
            )
            return payment_internal_error_response(
                payment_request=payment_request,
            )

        payload_response = payment_success_response(
            detail="پرداخت با موفقیت انجام شد.",
            code="payment_confirmed",
            payment_request=payment_request,
            payment=payment,
            http_status=status.HTTP_200_OK,
        )

        serializer = PaymentActionResponseSerializer(payload_response.data)
        return Response(serializer.data, status=payload_response.status_code)
