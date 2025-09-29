# credit/api/public/v1/views/statement.py
# ViewSet for statements + collection-level actions (add-purchase/add-payment/close-current).

import logging

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    extend_schema, OpenApiResponse,
    OpenApiExample,
)
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from credit.api.public.v1.serializers.credit import (
    StatementListSerializer,
    StatementDetailSerializer,
    CloseStatementResponseSerializer,
)
from credit.models.statement import Statement
from credit.services.use_cases import StatementUseCases
from wallets.models import Transaction
from wallets.utils.choices import TransactionStatus, WalletKind

logger = logging.getLogger(__name__)


@extend_schema(tags=["Credit Statements"])
class StatementViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    """
    list:     Paginated list of user's statements (year/month/created desc).
    retrieve: Statement details with lines (prefetched).
    add_purchase: POST /statements/add-purchase/   (collection action)
    add_payment:  POST /statements/add-payment/    (collection action)
    close_current:POST /statements/close-current/  (collection action)
    """
    lookup_field = "pk"

    # ---- queryset / serializers ----
    def get_queryset(self):
        # list: lightweight; retrieve: prefetch lines
        qs = Statement.objects.filter(user=self.request.user).order_by(
            "-year", "-month", "-created_at"
        )
        if self.action == "retrieve":
            qs = qs.prefetch_related("lines")
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return StatementListSerializer
        return StatementDetailSerializer

    # ---- collection actions ----

    @extend_schema(
        summary="Record a purchase from a successful transaction",
        description=(
                "Append a PURCHASE line to CURRENT statement of the buyer "
                "(transaction.from_wallet owner). Transaction must be SUCCESS and belong to the user."),
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "transaction_id": {"type": "integer"},
                    "description": {"type": "string", "default": "Purchase"},
                },
                "required": ["transaction_id"],
            }
        },
        responses={
            201: OpenApiResponse(
                description="Recorded",
                examples=[OpenApiExample("OK", value={"success": True})]
            ),
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Transaction not found"),
        },
        tags=["Credit Transactions"],
    )
    @action(detail=False, methods=["post"], url_path="add-purchase")
    def add_purchase(self, request, *args, **kwargs):
        """
        Validate ownership & credit-wallet constraints, then record a purchase on CURRENT statement.
        """
        user = request.user
        transaction_id = request.data.get("transaction_id")
        description = request.data.get("description") or "Purchase"

        if not transaction_id:
            return Response(
                {"error": "transaction_id is required"}, status=400
            )

        trx = get_object_or_404(
            Transaction.objects.select_related("from_wallet", "to_wallet"),
            pk=transaction_id
        )

        # Authorization + credit-wallet enforcement
        if not trx.from_wallet or trx.from_wallet.user_id != user.id:
            return Response(
                {"error": "transaction does not belong to user"}, status=403
            )
        if getattr(trx.from_wallet, "kind", None) != WalletKind.CREDIT:
            return Response(
                {"error": "transaction is not from a credit wallet"},
                status=400
            )

        if trx.status != TransactionStatus.SUCCESS:
            return Response(
                {"error": "transaction must be SUCCESS"}, status=400
            )

        try:
            StatementUseCases.record_successful_purchase_from_transaction(
                transaction_id=trx.id,
                description=description,
            )
            return Response({"success": True}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception("StatementViewSet.add_purchase error")
            return Response({"error": str(e)}, status=400)

    @extend_schema(
        summary="Record a payment on the current statement",
        description=(
                "Append a PAYMENT line to CURRENT statement. Positive amount is required. "
                "If transaction_id is provided, it must be SUCCESS and belong to the user."),
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "amount": {"type": "integer"},
                    "transaction_id": {"type": "integer"},
                    "description": {"type": "string", "default": "Payment"},
                },
                "required": ["amount"],
            }
        },
        responses={
            201: OpenApiResponse(
                description="Recorded",
                examples=[OpenApiExample("OK", value={"success": True})]
            ),
            400: OpenApiResponse(description="Validation error"),
        },
        tags=["Credit Transactions"],
    )
    @action(detail=False, methods=["post"], url_path="add-payment")
    def add_payment(self, request, *args, **kwargs):
        """
        Record a positive payment amount on CURRENT statement.
        Optionally link a SUCCESS transaction belonging to the user.
        """
        user = request.user
        raw_amount = request.data.get("amount")
        transaction_id = request.data.get("transaction_id")
        description = request.data.get("description") or "Payment"

        if raw_amount is None:
            return Response({"error": "amount is required"}, status=400)

        try:
            amount = int(raw_amount)
        except Exception:
            return Response({"error": "amount must be integer"}, status=400)
        if amount <= 0:
            return Response({"error": "amount must be > 0"}, status=400)

        trx = None
        if transaction_id:
            trx = get_object_or_404(
                Transaction.objects.select_related("from_wallet", "to_wallet"),
                pk=transaction_id
            )
            if trx.status != TransactionStatus.SUCCESS:
                return Response(
                    {"error": "transaction must be SUCCESS"}, status=400
                )
            if user.id not in (trx.from_wallet.user_id, trx.to_wallet.user_id):
                return Response(
                    {"error": "transaction does not belong to user"},
                    status=403
                )

        try:
            StatementUseCases.record_payment_on_current_statement(
                user=user,
                amount=amount,
                payment_transaction=trx,
                description=description,
            )
            return Response({"success": True}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception("StatementViewSet.add_payment error")
            return Response({"error": str(e)}, status=400)

    @extend_schema(
        summary="Close the current statement",
        description=("Close CURRENT statement and move it to PENDING_PAYMENT. "
                     "Due date will be set based on active credit limit's grace days."),
        responses={
            200: OpenApiResponse(
                description="Closed",
                examples=[OpenApiExample("OK", value={"success": True})]
            ),
            400: OpenApiResponse(description="No current statement"),
        },
        tags=["Credit Management"],
    )
    @action(
        detail=False, methods=["post"], url_path="close-current",
        serializer_class=CloseStatementResponseSerializer
    )
    def close_current(self, request, *args, **kwargs):
        """
        Close CURRENT statement; idempotent on non-current states.
        """
        user = request.user
        stmt = Statement.objects.get_current_statement(user)
        if not stmt:
            return Response({"error": "No current statement"}, status=400)
        try:
            stmt.close_statement()
            return Response({"success": True}, status=200)
        except Exception as e:
            logger.exception("StatementViewSet.close_current error")
            return Response({"error": str(e)}, status=400)
