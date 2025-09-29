# wallets/api/public/v1/views/payment.py
# ViewSet for Payment Requests: list, retrieve(by reference_code), and confirm action.

from django.utils.dateparse import parse_date, parse_datetime
from drf_spectacular.utils import (
    extend_schema, OpenApiResponse, OpenApiExample,
    OpenApiParameter, OpenApiTypes,
)
from rest_framework import status, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from wallets.api.public.v1.serializers import (
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
    """Try parse ISO datetime, fallback to ISO date, else None."""
    if not value:
        return None
    dt = parse_datetime(value)
    if dt:
        return dt
    d = parse_date(value)
    return d


@extend_schema(tags=["Wallet · Payment Requests"])
class PaymentRequestViewSet(
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
                "reference_code", "amount", "description", "status",
                "expires_at", "created_at", "store_id",
                "store__id", "store__name",
                "customer_id", "return_url",
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
        description="Returns details by `reference_code`. Includes `available_wallets` when authenticated.",
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
                        "status": "created",
                        "expires_at": "2025-09-27T12:34:56Z",
                    }
                )],
            ),
            400: OpenApiResponse(
                description="Payment request expired or invalid."
            ),
            404: OpenApiResponse(description="Payment request not found."),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        self.serializer_class = PaymentRequestDetailWithWalletsSerializer
        pr = self.get_object()
        # expire check
        try:
            check_and_expire_payment_request(pr)
        except Exception as e:
            return Response(
                {
                    "detail": str(e), "reference_code": pr.reference_code,
                    "return_url": pr.return_url
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
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
        },
        summary="Confirm & pay",
        description="Confirms and pays the payment request using the selected wallet.",
    )
    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, *args, **kwargs):
        pr = self.get_object()

        # expire check
        try:
            check_and_expire_payment_request(pr)
        except Exception as e:
            return Response(
                {
                    "detail": str(e), "reference_code": pr.reference_code,
                    "return_url": pr.return_url
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ser = PaymentConfirmSerializer(
            data=request.data, context={"request": request}
        )
        ser.is_valid(raise_exception=True)

        wallet_id = ser.validated_data["wallet_id"]
        try:
            wallet = Wallet.objects.get(
                id=wallet_id, user=request.user, owner_type=OwnerType.CUSTOMER
            )
        except Wallet.DoesNotExist:
            return Response(
                {"detail": "کیف پول پیدا نشد یا متعلق به شما نیست."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            txn = pay_payment_request(pr, request.user, wallet)
        except Exception as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

        payload = {
            "detail": "پرداخت با موفقیت انجام شد.",
            "payment_reference_code": pr.reference_code,
            "transaction_reference_code": txn.reference_code,
            "return_url": pr.return_url,
        }
        return Response(
            PaymentConfirmResponseSerializer(payload).data,
            status=status.HTTP_200_OK
        )
