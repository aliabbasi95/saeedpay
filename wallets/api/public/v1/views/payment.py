# wallets/api/public/v1/views/payment.py
# ViewSet for Payment Requests: list, retrieve(by reference_code), and confirm action.

from django.utils.dateparse import parse_date, parse_datetime
from drf_spectacular.utils import (
    extend_schema, OpenApiResponse, OpenApiExample,
    OpenApiParameter, OpenApiTypes,
)
from rest_framework import status, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from wallets.api.public.v1.serializers.payment import (
    PaymentRequestListItemSerializer,
    PaymentRequestDetailWithWalletsSerializer,
    PaymentConfirmSerializer,
    PaymentConfirmResponseSerializer,
)
from wallets.models import PaymentRequest, Wallet
from wallets.services.payment import (
    check_and_expire_payment_request, pay_payment_request,
)
from wallets.utils.choices import OwnerType

_ALLOWED_ORDERING = {"created_at", "-created_at", "amount", "-amount"}


def _parse_dt_maybe(value):
    """Try to parse ISO datetime, fallback to ISO date, else None."""
    if not value:
        return None
    dt = parse_datetime(value)
    if dt:
        return dt
    return parse_date(value)


def _error_response(detail, code, http_status, pr=None):
    """
    Build a uniform error payload. Optionally attach PR context.
    """
    payload = {"detail": detail, "code": code}
    if pr is not None:
        payload["reference_code"] = pr.reference_code
        payload["return_url"] = pr.return_url
    return Response(payload, status=http_status)


@extend_schema(tags=["Wallet · Payment Requests"])
class PaymentRequestViewSet(
    ScopedThrottleByActionMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    """
    list:     Paginated list of the authenticated user's payment requests.
    retrieve: Details by reference_code (includes available_wallets for authenticated user).
    confirm:  POST /payment-requests/{reference_code}/confirm/ to pay using a wallet.
    """
    lookup_field = "reference_code"
    lookup_value_regex = r"[-A-Za-z0-9_]+"
    throttle_scope_map = {
        "default": "user",
        "confirm": "payment-confirm",
        "retrieve": "user",
        "list": "user",
    }

    def get_queryset(self):
        user = self.request.user
        customer = getattr(user, "customer", None)
        if not customer:
            # Authenticated but no Customer yet -> empty list
            return PaymentRequest.objects.none()

        params = self.request.query_params
        qs = (
            PaymentRequest.objects
            .select_related("store")
            .only(
                "reference_code",
                "amount",
                "description",
                "status",
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

        # Filters
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

        # Safe ordering
        ordering = params.get("ordering") or "-created_at"
        if ordering not in _ALLOWED_ORDERING:
            ordering = "-created_at"
        return qs.order_by(ordering)

    # ---------- list ----------
    @extend_schema(
        summary="List user's payment requests",
        description=(
                "Returns a paginated list of the authenticated user's payment requests. "
                "Filters: status, store_id, q (reference_code icontains), created/expires ranges. "
                "Use retrieve endpoint to get `available_wallets`."
        ),
        parameters=[
            OpenApiParameter(
                "status", OpenApiParameter.QUERY, OpenApiTypes.STR,
                description="e.g. created, completed, expired"
            ),
            OpenApiParameter(
                "store_id", OpenApiParameter.QUERY, OpenApiTypes.INT,
                description="Filter by store id"
            ),
            OpenApiParameter(
                "q", OpenApiParameter.QUERY, OpenApiTypes.STR,
                description="Search in reference_code (icontains)"
            ),
            OpenApiParameter(
                "created_from", OpenApiParameter.QUERY, OpenApiTypes.STR,
                description="ISO date/datetime (created_at >= value)"
            ),
            OpenApiParameter(
                "created_to", OpenApiParameter.QUERY, OpenApiTypes.STR,
                description="ISO date/datetime (created_at <= value)"
            ),
            OpenApiParameter(
                "expires_from", OpenApiParameter.QUERY, OpenApiTypes.STR,
                description="ISO date/datetime (expires_at >= value)"
            ),
            OpenApiParameter(
                "expires_to", OpenApiParameter.QUERY, OpenApiTypes.STR,
                description="ISO date/datetime (expires_at <= value)"
            ),
            OpenApiParameter(
                "ordering", OpenApiParameter.QUERY, OpenApiTypes.STR,
                description="One of: -created_at, created_at, -amount, amount (default: -created_at)"
            ),
        ],
        responses={200: PaymentRequestListItemSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        self.serializer_class = PaymentRequestListItemSerializer
        return super().list(request, *args, **kwargs)

    # ---------- retrieve ----------
    @extend_schema(
        summary="Get payment request details",
        description=(
                "Returns details by `reference_code`. Includes `available_wallets` when authenticated. "
                "Expired requests are returned with status=expired."
        ),
        responses={
            200: OpenApiResponse(
                response=PaymentRequestDetailWithWalletsSerializer,
                examples=[OpenApiExample(
                    "Sample", value={
                        "reference_code": "PR123456",
                        "amount": 10000,
                        "description": "Purchase",
                        "store_id": 42,
                        "store_name": "Demo Store",
                        "status": "expired",
                        "status_display": "منقضی‌شده",
                        "expires_at": "2025-09-27T12:34:56Z",
                        "paid_at": None,
                        "can_pay": False,
                        "reason": "expired",
                        "available_wallets": [],
                    }
                )],
            ),
            404: OpenApiResponse(description="Payment request not found."),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        self.serializer_class = PaymentRequestDetailWithWalletsSerializer
        pr = self.get_object()

        # Mark expiry if needed, but do NOT raise in retrieve
        check_and_expire_payment_request(pr, raise_exception=False)

        serializer = self.get_serializer(pr, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ---------- confirm ----------
    @extend_schema(
        request=PaymentConfirmSerializer,
        responses={
            200: PaymentConfirmResponseSerializer,
            400: OpenApiResponse(
                description="Validation error or business rule violation."
            ),
            404: OpenApiResponse(description="Payment request not found."),
            410: OpenApiResponse(description="Payment request expired."),
        },
        summary="Confirm & pay",
        description="Confirms and pays the payment request using the selected wallet. Returns 410 if expired.",
    )
    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, *args, **kwargs):
        pr = self.get_object()

        # Expiry check → map to 410 on 'expired'
        try:
            check_and_expire_payment_request(pr)  # raises with code='expired'
        except ValidationError as e:
            if getattr(e, "code", None) == "expired":
                return _error_response(
                    "درخواست پرداخت منقضی شده است.", "expired",
                    status.HTTP_410_GONE, pr
                )
            return _error_response(
                str(e), "validation_error", status.HTTP_400_BAD_REQUEST, pr
            )
        except Exception as e:
            return _error_response(
                str(e), "unknown_error", status.HTTP_400_BAD_REQUEST, pr
            )

        # Validate input
        ser = PaymentConfirmSerializer(
            data=request.data, context={"request": request}
        )
        ser.is_valid(raise_exception=True)

        # Ownership check
        wallet_id = ser.validated_data["wallet_id"]
        try:
            wallet = Wallet.objects.get(
                id=wallet_id, user=request.user, owner_type=OwnerType.CUSTOMER
            )
        except Wallet.DoesNotExist:
            return _error_response(
                "کیف پول پیدا نشد یا متعلق به شما نیست.", "wallet_not_owned",
                status.HTTP_400_BAD_REQUEST, pr
            )

        # Pay
        try:
            txn = pay_payment_request(pr, request.user, wallet)
        except ValidationError as e:
            code = getattr(e, "code", "validation_error")
            return _error_response(
                str(e), code, status.HTTP_400_BAD_REQUEST, pr
            )
        except Exception as e:
            return _error_response(
                str(e), "business_rule", status.HTTP_400_BAD_REQUEST, pr
            )

        txn_ref = getattr(txn, "reference_code", None)

        if not txn_ref:
            try:
                last_txn = pr.transaction_set.order_by("-created_at").first()
                if last_txn:
                    txn_ref = last_txn.reference_code
            except Exception:
                pass

        if not txn_ref:
            try:
                from credit.models.authorization import \
                    CreditAuthorization as Auth
                auth = Auth.objects.filter(
                    payment_request=pr, status=Auth.Status.ACTIVE
                ) \
                    .order_by("-created_at").first()
                if auth:
                    txn_ref = auth.reference_code
            except Exception:
                pass

        if not txn_ref:
            txn_ref = ""

        payload = {
            "detail": "پرداخت با موفقیت انجام شد.",
            "payment_reference_code": pr.reference_code,
            "transaction_reference_code": txn_ref,
            "return_url": pr.return_url,
        }

        return Response(
            PaymentConfirmResponseSerializer(payload).data,
            status=status.HTTP_200_OK
        )
