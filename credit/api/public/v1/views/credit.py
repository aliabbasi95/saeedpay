# credit/api/public/v1/views/credit.py

import logging

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from credit.api.public.v1.serializers import (
    CreditLimitSerializer,
    StatementListSerializer,
    StatementDetailSerializer,
    StatementLineSerializer,
    CloseStatementResponseSerializer,
)
from credit.api.public.v1.views.schema import (
    credit_limit_list_schema,
    credit_limit_detail_schema,
    statement_list_schema,
    statement_detail_schema,
    statement_line_list_schema,
    add_purchase_schema,
    add_payment_schema,
    close_statement_schema,
)
from credit.models.credit_limit import CreditLimit
from credit.models.statement import Statement
from credit.models.statement_line import StatementLine
from credit.services.use_cases import StatementUseCases
from wallets.models import Transaction
from wallets.utils.choices import TransactionStatus, WalletKind

logger = logging.getLogger(__name__)


# ---------- Credit Limits ----------

@credit_limit_list_schema
class CreditLimitListView(generics.ListAPIView):
    """List all credit limits for the authenticated user, newest first. Unpaginated by design."""
    serializer_class = CreditLimitSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return (
            CreditLimit.objects
            .filter(user=self.request.user)
            .order_by("-created_at")
        )


@credit_limit_detail_schema
class CreditLimitDetailView(generics.RetrieveAPIView):
    serializer_class = CreditLimitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CreditLimit.objects.filter(user=self.request.user)


# ---------- Statements ----------

@statement_list_schema
class StatementListView(generics.ListAPIView):
    """Paginated list of user's statements, ordered by year, month, then creation (desc)."""
    serializer_class = StatementListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Statement.objects
            .filter(user=self.request.user)
            .order_by("-year", "-month", "-created_at")
        )


@statement_detail_schema
class StatementDetailView(generics.RetrieveAPIView):
    serializer_class = StatementDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Statement.objects
            .filter(user=self.request.user)
            .prefetch_related("lines")
        )


# ---------- Statement Lines ----------

@statement_line_list_schema
class StatementLineListView(generics.ListAPIView):
    """Paginated list of user's statement lines; optionally filterable by ?statement_id=..."""
    serializer_class = StatementLineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = (
            StatementLine.objects
            .filter(statement__user=self.request.user)
            .select_related("statement", "transaction")
            .order_by("-created_at")
        )
        statement_id = self.request.query_params.get("statement_id")
        if statement_id is not None:
            try:
                sid = int(statement_id)
            except (TypeError, ValueError):
                return StatementLine.objects.none()
            qs = qs.filter(statement_id=sid)

        return qs


# ---------- Transactions on Statements ----------

class AddPurchaseView(APIView):
    permission_classes = [IsAuthenticated]

    @add_purchase_schema
    def post(self, request):
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
            logger.exception("AddPurchaseView error")
            return Response({"error": str(e)}, status=400)


class AddPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    @add_payment_schema
    def post(self, request):
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
            logger.exception("AddPaymentView error")
            return Response({"error": str(e)}, status=400)


class CloseStatementView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CloseStatementResponseSerializer

    @close_statement_schema
    def post(self, request):
        user = request.user
        stmt = Statement.objects.get_current_statement(user)
        if not stmt:
            return Response({"error": "No current statement"}, status=400)
        try:
            stmt.close_statement()
            return Response({"success": True}, status=200)
        except Exception as e:
            logger.exception("CloseStatementView error")
            return Response({"error": str(e)}, status=400)
