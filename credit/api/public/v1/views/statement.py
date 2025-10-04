# credit/api/public/v1/views/statement.py

import logging

from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from credit.api.public.v1.schema import (
    statement_viewset_schema,
    add_purchase_schema,
    add_payment_schema,
    close_current_schema,
)
from credit.api.public.v1.serializers.credit import (
    StatementListSerializer,
    StatementDetailSerializer,
)
from credit.models.statement import Statement
from credit.services.use_cases import StatementUseCases
from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from wallets.models import Transaction
from wallets.utils.choices import TransactionStatus, WalletKind

logger = logging.getLogger(__name__)


@statement_viewset_schema
class StatementViewSet(
    ScopedThrottleByActionMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    list:     Paginated list of user's statements (year/month/created desc).
    retrieve: Statement details with lines (prefetched).
    """
    lookup_field = "pk"
    throttle_scope_map = {
        "default": "credit-statements-read",
        "list": "credit-statements-read",
        "retrieve": "credit-statements-read",
        "add_purchase": "credit-statements-write",
        "add_payment": "credit-statements-write",
        "close_current": "credit-statements-write",
    }

    # ---- queryset / serializers ----
    def get_queryset(self):
        qs = Statement.objects.filter(user=self.request.user).order_by(
            "-year", "-month", "-created_at"
        )
        if self.action == "retrieve":
            qs = qs.prefetch_related("lines")
        return qs

    def get_serializer_class(self):
        return StatementListSerializer if self.action == "list" else StatementDetailSerializer

    # ---- small helpers ----
    @staticmethod
    def _bad_request(detail: str):
        return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def _forbidden(detail: str):
        return Response({"detail": detail}, status=status.HTTP_403_FORBIDDEN)

    # ---- collection actions ----

    @add_purchase_schema
    @action(detail=False, methods=["post"], url_path="add-purchase")
    def add_purchase(self, request, *args, **kwargs):
        """Validate ownership & credit-wallet constraints, then record a purchase on CURRENT statement."""
        transaction_id = request.data.get("transaction_id")
        description = (request.data.get("description") or "Purchase").strip()

        if not transaction_id:
            return self._bad_request("transaction_id is required")

        trx = get_object_or_404(
            Transaction.objects.select_related("from_wallet", "to_wallet"),
            pk=transaction_id
        )

        if not trx.from_wallet or trx.from_wallet.user_id != request.user.id:
            return self._forbidden("Transaction does not belong to user.")
        if getattr(trx.from_wallet, "kind", None) != WalletKind.CREDIT:
            return self._bad_request(
                "Transaction is not from a credit wallet."
            )
        if trx.status != TransactionStatus.SUCCESS:
            return self._bad_request("Transaction must be SUCCESS.")

        try:
            StatementUseCases.record_successful_purchase_from_transaction(
                transaction_id=trx.id,
                description=description or "Purchase",
            )
            return Response({"success": True}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception("StatementViewSet.add_purchase error")
            return self._bad_request(str(e))

    @add_payment_schema
    @action(detail=False, methods=["post"], url_path="add-payment")
    def add_payment(self, request, *args, **kwargs):
        """Record a positive payment amount on CURRENT statement; optionally link a SUCCESS transaction."""
        raw_amount = request.data.get("amount")
        transaction_id = request.data.get("transaction_id")
        description = (request.data.get("description") or "Payment").strip()

        if raw_amount is None:
            return self._bad_request("amount is required")
        try:
            amount = int(raw_amount)
        except Exception:
            return self._bad_request("amount must be integer")
        if amount <= 0:
            return self._bad_request("amount must be > 0")

        trx = None
        if transaction_id:
            trx = get_object_or_404(
                Transaction.objects.select_related("from_wallet", "to_wallet"),
                pk=transaction_id
            )
            if trx.status != TransactionStatus.SUCCESS:
                return Response(
                    {"error": "transaction must be SUCCESS"},
                    status=400
                )
            if request.user.id not in (
                    trx.from_wallet.user_id, trx.to_wallet.user_id
            ):
                return Response(
                    {"error": "transaction does not belong to user"},
                    status=403
                )

        try:
            StatementUseCases.record_payment_on_current_statement(
                user=request.user,
                amount=amount,
                payment_transaction=trx,
                description=description or "Payment",
            )
            return Response({"success": True}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception("StatementViewSet.add_payment error")
            return self._bad_request(str(e))

    @close_current_schema
    @action(detail=False, methods=["post"], url_path="close-current")
    def close_current(self, request, *args, **kwargs):
        """Close CURRENT statement; idempotent on non-current states."""
        stmt = Statement.objects.get_current_statement(request.user)
        if not stmt:
            return self._bad_request("No current statement.")
        try:
            stmt.close_statement()
            return Response({"success": True}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("StatementViewSet.close_current error")
            return self._bad_request(str(e))
