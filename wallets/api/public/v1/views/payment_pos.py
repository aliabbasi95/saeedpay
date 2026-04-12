# wallets/api/public/v1/views/payment_pos.py

from django.conf import settings
from django.http import Http404
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from merchants.permissions import IsMerchant
from store.models import Store
from wallets.api.payment_responses import (
    build_payment_response_payload,
    payment_error_response,
    payment_success_response,
)
from wallets.api.public.v1.schema import (
    merchant_pos_payment_cancel_schema,
    merchant_pos_payment_create_schema,
    merchant_pos_payment_list_schema,
    merchant_pos_payment_retrieve_schema,
)
from wallets.api.public.v1.serializers.payment_pos import (
    MerchantPosPaymentRequestCreateResponseSerializer,
    MerchantPosPaymentRequestCreateSerializer,
    MerchantPosPaymentRequestDetailSerializer,
    MerchantPosPaymentRequestListItemSerializer,
)
from wallets.models import PaymentRequest
from wallets.services.payment.payment_request_service import (
    cancel_payment_request,
    check_and_expire_payment_request,
    create_payment_request,
)
from wallets.utils.choices import PaymentFlowType
from wallets.utils.consts import FRONTEND_PAYMENT_DETAIL_URL

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


class MerchantPosPaymentRequestViewSet(
    ScopedThrottleByActionMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, IsMerchant]
    lookup_field = "reference_code"
    lookup_value_regex = r"[-A-Za-z0-9_]+"
    throttle_scope_map = {
        "default": "merchant-pos-payment-read",
        "create": "merchant-pos-payment-write",
        "list": "merchant-pos-payment-read",
        "retrieve": "merchant-pos-payment-read",
        "cancel": "merchant-pos-payment-write",
    }

    def _get_owned_store(self, *, store_id, user):
        merchant = getattr(user, "merchant", None)
        if not merchant:
            return None

        return Store.objects.filter(
            id=store_id,
            merchant=merchant,
        ).first()

    def get_queryset(self):
        qs = PaymentRequest.objects.select_related(
            "store",
            "paid_by",
            "paid_wallet",
        ).filter(flow_type=PaymentFlowType.QR_POS)

        if self.action == "list":
            qs = qs.filter(store__merchant=self.request.user.merchant)

            params = self.request.query_params

            store_id = params.get("store_id")
            if store_id:
                qs = qs.filter(store_id=store_id)

            status_param = params.get("status")
            if status_param:
                qs = qs.filter(status=status_param)

            q = params.get("q")
            if q:
                qs = qs.filter(reference_code__icontains=q)

            created_from = _parse_dt_maybe(params.get("created_from"))
            if created_from:
                qs = qs.filter(created_at__gte=created_from)

            created_to = _parse_dt_maybe(params.get("created_to"))
            if created_to:
                qs = qs.filter(created_at__lte=created_to)

            ordering = params.get("ordering") or "-created_at"
            if ordering not in _ALLOWED_ORDERING:
                ordering = "-created_at"
            qs = qs.order_by(ordering)

        return qs

    def get_object(self):
        obj = super().get_object()
        merchant = getattr(self.request.user, "merchant", None)

        if obj.store.merchant_id != getattr(merchant, "id", None):
            raise Http404

        return obj

    def get_serializer_class(self):
        if self.action == "create":
            return MerchantPosPaymentRequestCreateSerializer
        if self.action == "list":
            return MerchantPosPaymentRequestListItemSerializer
        return MerchantPosPaymentRequestDetailSerializer

    @merchant_pos_payment_create_schema
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        store = self._get_owned_store(
            store_id=data["store_id"],
            user=request.user,
        )
        if not store:
            return payment_error_response(
                detail="فروشگاه پیدا نشد یا متعلق به شما نیست.",
                code="store_not_found",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        if not store.is_active:
            return payment_error_response(
                detail="فروشگاه غیرفعال است.",
                code="inactive_store",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        payment_request = create_payment_request(
            store=store,
            customer=None,
            amount=data["amount"],
            return_url=None,
            description=data.get("description", ""),
            external_guid=None,
            flow_type=PaymentFlowType.QR_POS,
            actor=request.user,
        )

        payment_url = (
            f"{settings.FRONTEND_BASE_URL}"
            f"{FRONTEND_PAYMENT_DETAIL_URL}"
            f"{payment_request.reference_code}/"
        )

        payload = build_payment_response_payload(
            detail="درخواست پرداخت حضوری با موفقیت ایجاد شد.",
            code="payment_request_created",
            payment_request=payment_request,
            next_action="scan_qr",
            merchant_confirmation_required=False,
            extra={
                "payment_request_id": payment_request.id,
                "flow_type": payment_request.flow_type,
                "payment_url": payment_url,
                "qr_payload": payment_request.reference_code,
                "store_id": store.id,
                "store_name": store.name,
            },
        )

        response_serializer = MerchantPosPaymentRequestCreateResponseSerializer(
            payload
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @merchant_pos_payment_list_schema
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @merchant_pos_payment_retrieve_schema
    def retrieve(self, request, *args, **kwargs):
        payment_request = self.get_object()
        check_and_expire_payment_request(payment_request, raise_exception=False)
        payment_request.refresh_from_db()

        serializer = self.get_serializer(payment_request)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @merchant_pos_payment_cancel_schema
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, *args, **kwargs):
        payment_request = self.get_object()

        try:
            cancelled_request = cancel_payment_request(
                payment_request=payment_request,
                store=payment_request.store,
                actor=request.user,
            )
            cancelled_request.refresh_from_db()
        except ValidationError as exc:
            return payment_error_response(
                detail=str(exc),
                code=_extract_validation_code(exc),
                http_status=status.HTTP_400_BAD_REQUEST,
                payment_request=payment_request,
            )
        except Exception as exc:
            return payment_error_response(
                detail=str(exc),
                code="business_rule",
                http_status=status.HTTP_400_BAD_REQUEST,
                payment_request=payment_request,
            )

        payload_response = payment_success_response(
            detail="درخواست پرداخت حضوری با موفقیت لغو شد.",
            code="payment_request_cancelled",
            payment_request=cancelled_request,
            http_status=status.HTTP_200_OK,
            next_action="none",
            merchant_confirmation_required=False,
        )
        return Response(
            payload_response.data,
            status=payload_response.status_code,
        )
