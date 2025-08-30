# credit/api/public/v1/views/credit.py

import logging

from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from credit.api.public.v1.serializers.credit import (
    CreditLimitSerializer,
    StatementListSerializer,
    StatementDetailSerializer,
    StatementLineSerializer,
    ApplyPenaltyResponseSerializer,
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
    apply_penalty_schema,
    close_statement_schema,
    risk_score_schema,
)
from credit.models.credit_limit import CreditLimit
from credit.models.statement import Statement
from credit.models.statement_line import StatementLine
from credit.utils.risk_scoring import RiskScoringEngine
from wallets.models import Transaction
from wallets.utils.choices import TransactionStatus

logger = logging.getLogger(__name__)


# --- CreditLimit Views ---


@credit_limit_list_schema
class CreditLimitListView(generics.ListAPIView):
    """
    List user's credit limits.

    This view provides access to all credit limits belonging to the authenticated user.
    Credit limits define the maximum amount a user can spend on credit and track
    their current usage and availability.
    """

    queryset = CreditLimit.objects.all()
    serializer_class = CreditLimitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return CreditLimit.objects.filter(user=user).order_by("-created_at")


@credit_limit_detail_schema
class CreditLimitDetailView(generics.RetrieveAPIView):
    """
    Get credit limit details.

    This view provides detailed information about a specific credit limit
    belonging to the authenticated user, including all limit information,
    usage statistics, and status details.
    """

    queryset = CreditLimit.objects.all()
    serializer_class = CreditLimitSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        user = self.request.user
        return CreditLimit.objects.filter(user=user)


# --- Statement Views ---


@statement_list_schema
class StatementListView(generics.ListAPIView):
    """
    List user's credit statements.

    This view provides a lightweight list of all credit statements belonging to
    the authenticated user. Returns minimal statement information without detailed
    line items for optimal performance. Use the detail endpoint to get complete
    statement information including all transactions.
    """

    serializer_class = StatementListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Order by most recent first for better UX
        return Statement.objects.filter(user=user).order_by(
            "-year", "-month", "-created_at"
        )


@statement_detail_schema
class StatementDetailView(generics.RetrieveAPIView):
    """
    Get credit statement details.

    This view provides detailed information about a specific credit statement
    including all statement lines (transactions). Only returns statements
    belonging to the authenticated user with complete transaction history.
    """

    serializer_class = StatementDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        user = self.request.user
        # Prefetch related lines to avoid N+1 queries when accessing lines
        return Statement.objects.filter(user=user).prefetch_related("lines")


# --- StatementLine Views ---


@statement_line_list_schema
class StatementLineListView(generics.ListAPIView):
    """
    List user's statement lines.

    This view provides access to all statement lines (transactions) belonging to
    the authenticated user. Statement lines represent individual transactions within
    credit statements including purchases, payments, fees, and penalties.
    Results can be filtered by statement_id for specific statement transactions.
    """

    serializer_class = StatementLineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Optimize query with select_related to avoid N+1 queries
        queryset = StatementLine.objects.filter(
            statement__user=user
        ).select_related(
            "statement"
        )

        # Allow filtering by statement_id if provided
        statement_id = self.request.query_params.get("statement_id")
        if statement_id:
            queryset = queryset.filter(statement_id=statement_id)

        return queryset.order_by("-created_at")


# --- Add Purchase/Payment API ---


class AddPurchaseView(APIView):
    """
    Add purchase to credit statement.

    This view processes purchase transactions and adds them to the user's current
    credit statement. If no current statement exists, a new one will be created
    automatically. The transaction must be valid and belong to the authenticated user.
    """

    permission_classes = [IsAuthenticated]

    @add_purchase_schema
    def post(self, request):
        user = request.user
        transaction_id = request.data.get("transaction_id")
        if not transaction_id:
            return Response(
                {"error": "transaction_id is required"}, status=400
            )
        transaction = get_object_or_404(Transaction, id=transaction_id)

        try:
            from wallets.utils.choices import WalletKind
            if getattr(
                    transaction.from_wallet, "kind", None
            ) != WalletKind.CREDIT:
                return Response(
                    {"error": "not a credit-wallet purchase"}, status=400
                )
            statement = Statement.objects.get_current_statement(user)
            if not statement:
                prev_stmt = (
                    Statement.objects.filter(user=user)
                    .exclude(status="current")
                    .order_by("-year", "-month")
                    .first()
                )
                starting_balance = prev_stmt.closing_balance if prev_stmt else 0
                statement, _ = Statement.objects.get_or_create_current_statement(
                    user, starting_balance=starting_balance
                )
            statement.add_transaction(transaction)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)
        return Response({"success": True}, status=201)


class AddPaymentView(APIView):
    """
    Add payment to credit statement.

    This view processes payment transactions and applies them to the user's current
    credit statement. Payments reduce the outstanding balance and are validated
    before being applied to ensure transaction integrity.
    """

    permission_classes = [IsAuthenticated]

    @add_payment_schema
    def post(self, request):
        user = request.user
        amount = request.data.get("amount")
        transaction_id = request.data.get("transaction_id")
        if not amount:
            return Response({"error": "amount is required"}, status=400)
        try:
            amount = int(amount)
        except Exception:
            return Response({"error": "amount must be integer"}, status=400)
        if amount <= 0:
            return Response({"error": "amount must be > 0"}, status=400)
        transaction = None
        if transaction_id:
            transaction = get_object_or_404(Transaction, id=transaction_id)
            # Validate transaction for payments as well
            if (
                    hasattr(transaction, "status")
                    and transaction.status != TransactionStatus.SUCCESS
            ):
                return Response(
                    {"error": "invalid or unsuccessful transaction"},
                    status=400
                )
            if not (
                    transaction.from_wallet.user_id == user.id
                    or transaction.to_wallet.user_id == user.id
            ):
                return Response(
                    {"error": "transaction does not belong to user"},
                    status=400
                )
        # Apply payment to current statement
        curr = Statement.objects.get_current_statement(user)
        if not curr:
            return Response({"error": "No current statement"}, status=400)
        curr.apply_payment(amount, transaction)
        return Response({"success": True, "applied_to": "current"}, status=201)


# --- Penalty Application API ---
class ApplyPenaltyView(APIView):
    """
    Apply penalty to overgrace statement.

    This view calculates and applies penalty charges to the user's latest pending
    or overgrace statement. Penalties are calculated based on the overgrace amount
    and number of days past the due date.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ApplyPenaltyResponseSerializer

    @apply_penalty_schema
    def post(self, request):
        user = request.user
        # Target latest pending statement that is overgrace
        statement = (
            Statement.objects.filter(
                user=user, status__in=["pending_payment", "overgrace"]
            )
            .order_by("-year", "-month")
            .first()
        )
        if not statement:
            return Response(
                {"error": "No pending or overgrace statement"}, status=400
            )
        penalty_amount = statement.calculate_and_apply_penalty()
        if penalty_amount > 0:
            pass
        return Response({"penalty_applied": penalty_amount}, status=200)


# --- Statement Closing API ---
class CloseStatementView(APIView):
    """
    Close current credit statement.

    This view closes the user's current credit statement and transitions it to
    pending_payment status. This action finalizes the statement for the current
    period and sets up the due date for payment.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = CloseStatementResponseSerializer

    @close_statement_schema
    def post(self, request):
        user = request.user
        statement = Statement.objects.get_current_statement(user)
        if not statement:
            return Response({"error": "No current statement"}, status=400)
        statement.close_statement()
        return Response({"success": True}, status=200)


# --- Risk Scoring API ---
class RiskScoreView(APIView):
    """
    Get user's credit risk score.

    This view calculates and returns the user's current credit risk score based on
    payment history, outstanding balances, and other credit behavior factors.
    Higher scores indicate lower risk and are used for credit decisions.
    """

    permission_classes = [IsAuthenticated]

    @risk_score_schema
    def get(self, request):
        user = request.user
        engine = RiskScoringEngine()
        score = engine.calculate_score(user)
        return Response({"risk_score": score}, status=200)
