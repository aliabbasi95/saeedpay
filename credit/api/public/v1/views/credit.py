from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from credit.models.credit_limit import CreditLimit
from credit.models.statement import Statement
from credit.models.statement_line import StatementLine
from credit.api.public.v1.serializers.credit import CreditLimitSerializer, StatementSerializer, StatementLineSerializer
from wallets.models import Transaction
from credit.utils.risk_scoring import get_risk_score
from django.utils import timezone
from persiantools.jdatetime import JalaliDateTime
from django.db.models import Sum

# --- CreditLimit Views ---

class CreditLimitListView(generics.ListAPIView):
    queryset = CreditLimit.objects.all()
    serializer_class = CreditLimitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return CreditLimit.objects.filter(user=user)

class CreditLimitDetailView(generics.RetrieveAPIView):
    queryset = CreditLimit.objects.all()
    serializer_class = CreditLimitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return CreditLimit.objects.filter(user=user)

# --- Statement Views ---

class StatementListView(generics.ListAPIView):
    serializer_class = StatementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Statement.objects.filter(user=user)

class StatementDetailView(generics.RetrieveAPIView):
    serializer_class = StatementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Statement.objects.filter(user=user)

# --- StatementLine Views ---

class StatementLineListView(generics.ListAPIView):
    serializer_class = StatementLineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return StatementLine.objects.filter(statement__user=user)

# --- Add Purchase/Payment API ---
from rest_framework.views import APIView

class AddPurchaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        amount = request.data.get('amount')
        transaction_id = request.data.get('transaction_id')
        description = request.data.get('description', '')
        if not amount or not transaction_id:
            return Response({'error': 'amount and transaction_id are required'}, status=400)
        transaction = get_object_or_404(Transaction, id=transaction_id)
        statement, _ = Statement.objects.get_or_create_current_statement(user)
        statement.add_transaction(transaction)
        statement.update_balances()
        return Response({'success': True}, status=201)

class AddPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        amount = request.data.get('amount')
        transaction_id = request.data.get('transaction_id')
        if not amount:
            return Response({'error': 'amount is required'}, status=400)
        try:
            amount = int(amount)
        except Exception:
            return Response({'error': 'amount must be integer'}, status=400)
        if amount <= 0:
            return Response({'error': 'amount must be > 0'}, status=400)
        transaction = None
        if transaction_id:
            transaction = get_object_or_404(Transaction, id=transaction_id)
        # Prefer paying previous pending statement within grace to reduce carryover
        prev_stmt = Statement.objects.filter(user=user, status='pending_payment').order_by('-year', '-month').first()
        if prev_stmt and prev_stmt.is_within_grace():
            # 1) Apply payment to previous statement
            prev_stmt.apply_payment(amount, transaction)
            prev_stmt.update_balances()

            # 2) Adjust current statement's carryover by the paid amount (up to remaining carryover)
            curr_stmt, _ = Statement.objects.get_or_create_current_statement(user)
            carry_qs = curr_stmt.lines.filter(type__in=['carryover', 'carryover_adjustment'])
            carry_sum = carry_qs.aggregate(total=Sum('amount'))['total'] or 0
            remaining_carryover = -carry_sum if carry_sum < 0 else 0  # positive number to offset
            adjust_amount = min(amount, remaining_carryover)
            if adjust_amount > 0:
                desc = f"تعدیل انتقال بابت پرداخت صورتحساب {prev_stmt.year}/{prev_stmt.month:02d}"
                curr_stmt.apply_carryover_adjustment(adjust_amount, description=desc)
                curr_stmt.update_balances()
            return Response({
                'success': True,
                'applied_to': 'previous_within_grace',
                'adjusted_on_current': adjust_amount
            }, status=201)

        # Otherwise, pay current statement directly
        curr = Statement.objects.get_current_statement(user)
        if not curr:
            return Response({'error': 'No current statement'}, status=400)
        curr.apply_payment(amount, transaction)
        curr.update_balances()
        return Response({'success': True, 'applied_to': 'current'}, status=201)

# --- Penalty Application API ---
class ApplyPenaltyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        statement = Statement.objects.get_current_statement(user)
        if not statement:
            return Response({'error': 'No current statement'}, status=400)
        penalty_amount = statement.calculate_penalty()
        if penalty_amount > 0:
            statement.apply_penalty(penalty_amount)
            statement.update_balances()
        return Response({'penalty_applied': penalty_amount}, status=200)

# --- Statement Closing API ---
class CloseStatementView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        statement = Statement.objects.get_current_statement(user)
        if not statement:
            return Response({'error': 'No current statement'}, status=400)
        statement.close_statement()
        return Response({'success': True}, status=200)

# --- Risk Scoring API ---
class RiskScoreView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        score = get_risk_score(user)
        return Response({'risk_score': score}, status=200)
