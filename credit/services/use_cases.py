# credit/services/use_cases.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from credit.models import Statement
from credit.utils.choices import StatementStatus, StatementLineType
from wallets.models import Transaction as WalletTransaction
from wallets.utils.choices import TransactionStatus


@dataclass(frozen=True)
class FinalizeResult:
    finalized_count: int
    closed_without_penalty_count: int
    closed_with_penalty_count: int


class StatementUseCases:
    """
    High-level business use-cases for the statement workflow.

    Design principles implemented here:
      - After a statement is issued (moved to PENDING_PAYMENT), it is treated as an immutable snapshot.
      - All post-statement customer payments are recorded on the CURRENT statement.
      - At due-time finalization, we read payments made during [closed_at .. due_date] from CURRENT,
        decide the outcome for the PENDING statement, and if needed, add a penalty line to CURRENT.
      - Month-end rollover closes past CURRENT statements and creates the new CURRENT with carry-over,
        plus a monthly interest line on negative carry-overs.
    """

    # ---------- Purchases ----------

    @staticmethod
    @transaction.atomic
    def record_successful_purchase_from_transaction(
            transaction_id: int,
            *,
            description: str = "Purchase",
    ) -> Statement:
        """
        Read a SUCCESS wallets.Transaction and append a PURCHASE line
        to the buyer's CURRENT statement (buyer = owner of `from_wallet`).

        Business validations specific to credit availability live in
        Statement.add_purchase(), so we delegate to it.
        """
        transaction_obj = (
            WalletTransaction.objects.select_related(
                "from_wallet", "to_wallet"
            )
            .get(pk=transaction_id)
        )

        if transaction_obj.status != TransactionStatus.SUCCESS:
            raise ValueError(
                "Transaction must be SUCCESS to be recorded as a purchase."
            )

        buyer_user = transaction_obj.from_wallet.user
        statement, _ = Statement.objects.get_or_create_current_statement(
            buyer_user
        )
        statement.add_purchase(
            transaction=transaction_obj, description=description
        )
        # Balances are recomputed via StatementLine.save() -> Statement.update_balances()
        return statement

    # ---------- Payments (always on CURRENT) ----------

    @staticmethod
    @transaction.atomic
    def record_payment_on_current_statement(
            user,
            amount: int,
            *,
            payment_transaction: Optional[WalletTransaction] = None,
            description: str = "Payment",
    ) -> Statement:
        """
        Record a customer payment on the CURRENT statement.
        Positive amount is normalized in StatementLine.save().
        """
        if int(amount) == 0:
            raise ValueError("Amount must be non-zero.")

        current_statement, _ = Statement.objects.get_or_create_current_statement(
            user
        )
        current_statement.add_line(
            type_=StatementLineType.PAYMENT,
            amount=abs(int(amount)),
            transaction=payment_transaction,
            description=description,
        )
        return current_statement

    # ---------- Month-end rollover ----------

    @staticmethod
    @transaction.atomic
    def perform_month_end_rollover() -> Dict[str, int]:
        """
        Close past-month CURRENT statements, create the new CURRENT with carry-over,
        and add a monthly interest line for negative carry-overs.
        """
        return Statement.objects.close_monthly_statements()

    # ---------- Due-window finalization ----------

    @staticmethod
    @transaction.atomic
    def finalize_due_windows(now=None) -> FinalizeResult:
        """
        For each PENDING_PAYMENT whose due_date has passed:
          1) Ensure there is a CURRENT statement for the user.
          2) Sum payments recorded on CURRENT within [closed_at .. due_date] of the pending statement.
          3) Decide statement outcome (closed_no_penalty / closed_with_penalty).
          4) If closed_with_penalty: compute penalty on the pending snapshot and add a PENALTY line to CURRENT.
             (Penalty is computed *before* status changes, because compute_penalty_amount depends on status.)
        """
        now = now or timezone.localtime(timezone.now())

        pending_candidates = (
            Statement.objects
            .select_for_update()
            .filter(status=StatementStatus.PENDING_PAYMENT, due_date__lt=now)
            .order_by("user_id", "year", "month")
        )

        finalized_count = 0
        closed_without_penalty_count = 0
        closed_with_penalty_count = 0

        for pending_statement in pending_candidates:
            current_statement = Statement.objects.get_current_statement(
                pending_statement.user
            )
            if not current_statement:
                current_statement, _ = Statement.objects.get_or_create_current_statement(
                    pending_statement.user, starting_balance=0
                )

            total_payments_amount = StatementUseCases._sum_payments_on_current_during_window(
                current_statement=current_statement,
                start=pending_statement.closed_at,
                end=pending_statement.due_date,
            )

            # Decide outcome (replicates Statement.determine_due_outcome() decision to know if penalty is needed)
            minimum_required = pending_statement.calculate_minimum_payment_amount()
            debt_amount = abs(
                int(pending_statement.closing_balance)
            ) if pending_statement.closing_balance < 0 else 0
            qualifies_for_penalty = (debt_amount > 0) and (
                    total_payments_amount < minimum_required)

            if qualifies_for_penalty:
                # Compute before status changes, because compute_penalty_amount checks status
                penalty_amount = pending_statement.compute_penalty_amount(
                    now=now
                )
                if penalty_amount > 0:
                    current_statement.add_line(
                        type_=StatementLineType.PENALTY,
                        amount=-int(penalty_amount),
                        description=f"Late penalty for {pending_statement.year}/{pending_statement.month:02d}",
                    )

            # Persist the final outcome on the pending snapshot
            outcome = pending_statement.determine_due_outcome(
                int(total_payments_amount)
            )

            finalized_count += 1
            if outcome == StatementStatus.CLOSED_NO_PENALTY:
                closed_without_penalty_count += 1
            else:
                closed_with_penalty_count += 1

        return FinalizeResult(
            finalized_count=finalized_count,
            closed_without_penalty_count=closed_without_penalty_count,
            closed_with_penalty_count=closed_with_penalty_count,
        )

    # ---------- Private helpers ----------

    @staticmethod
    def _sum_payments_on_current_during_window(
            *,
            current_statement: Statement,
            start,
            end,
    ) -> int:
        """
        Sum PAYMENT lines on CURRENT statement within [start .. end].
        """
        if not start or not end or end <= start:
            return 0

        return int(
            current_statement.lines
            .filter(
                type=StatementLineType.PAYMENT,
                created_at__gte=start,
                created_at__lte=end,
            )
            .aggregate(total=Sum("amount"))["total"] or 0
        )

    @staticmethod
    @transaction.atomic
    def record_successful_purchase_for_credit(
            *,
            user,
            amount: int,
            description: str = "Purchase (credit)",
    ) -> Statement:
        """
        Append a PURCHASE line to the user's CURRENT statement with the given amount.
        Use this when credit purchases are finalized without a wallets.Transaction movement.
        amount must be positive; it will be normalized to negative inside StatementLine.save().
        """
        if int(amount) <= 0:
            raise ValueError("Amount must be > 0 for a purchase.")

        statement, _ = Statement.objects.get_or_create_current_statement(user)
        statement.add_purchase(
            transaction=None, description=description, amount=amount
        )
        return statement
