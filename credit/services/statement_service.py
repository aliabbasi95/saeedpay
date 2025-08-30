# credit/services/statement_service.py

"""
Service functions for statement workflow automation
"""

import logging
from typing import List, Dict, Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from persiantools.jdatetime import JalaliDate

from credit.models import Statement
from credit.utils.choices import StatementStatus
from credit.utils.constants import (
    MONTHLY_INTEREST_RATE,
)

logger = logging.getLogger(__name__)

User = get_user_model()


def get_users_with_active_credit() -> List[User]:
    """Get all users with active credit limits"""
    return User.objects.filter(credit_limits__status="active").distinct()


def process_month_end_statements() -> Dict[str, Any]:
    with transaction.atomic():
        return Statement.objects.close_monthly_statements()


def process_pending_payments() -> Dict[str, Any]:
    logger.info("Starting pending payments processing")
    pending = Statement.objects.filter(
        status=StatementStatus.PENDING_PAYMENT
    ).select_related("user")
    processed = closed_no_penalty = closed_with_penalty = 0
    errors = []
    for st in pending:
        try:
            with transaction.atomic():
                if not st.is_in_grace_period:
                    outcome = st.process_payment_during_grace_period(0)
                    if outcome["status"] == "closed_no_penalty":
                        closed_no_penalty += 1
                    else:
                        closed_with_penalty += 1
                        # Late fee روی استیتمنت جاری
                        st.calculate_and_apply_penalty()
                    processed += 1
        except Exception as e:
            errors.append(f"statement {st.id}: {e}")
    return {
        "statements_processed": processed,
        "closed_no_penalty": closed_no_penalty,
        "closed_with_penalty": closed_with_penalty,
        "errors": errors,
    }


def calculate_user_interest(user: User) -> int:
    """
    Calculate interest for user's current statement
    Returns interest amount in Rials
    """
    try:
        current_statement = Statement.objects.get_current_statement(user)
        if not current_statement:
            return 0

        # Get previous statement to check for debt
        previous_statements = Statement.objects.filter(
            user=user,
            status__in=["pending_payment", "closed_no_penalty",
                        "closed_with_penalty"],
        ).order_by("-year", "-month")

        if not previous_statements.exists():
            return 0

        last_statement = previous_statements.first()
        outstanding_balance = (
            abs(last_statement.closing_balance)
            if last_statement.closing_balance < 0
            else 0
        )

        if outstanding_balance == 0:
            return 0

        interest_rate = MONTHLY_INTEREST_RATE
        interest_amount = int(outstanding_balance * interest_rate)

        logger.info(
            f"Calculated interest for user {user.id}: "
            f"{interest_amount} Rials on {outstanding_balance} debt"
        )

        return interest_amount

    except Exception as e:
        logger.error(
            f"Error calculating interest for user {user.id}: {str(e)}"
        )
        return 0


def add_interest_to_current_statement(user: User) -> bool:
    """
    Add interest line to user's current statement
    Returns True if interest was added, False otherwise
    """
    try:
        current_statement = Statement.objects.get_current_statement(user)
        if not current_statement:
            return False

        interest_amount = calculate_user_interest(user)
        if interest_amount <= 0:
            return False

        # Check if interest already exists for this statement
        existing_interest = current_statement.lines.filter(
            type="interest"
        ).exists()

        if existing_interest:
            return False

        current_statement.add_line(
            type="interest",
            amount=-interest_amount,
            description=f"سود ماهانه ({JalaliDate.today().strftime('%Y/%m')})",
        )

        logger.info(
            f"Added interest line to user {user.id} statement: "
            f"{interest_amount} Rials"
        )

        return True

    except Exception as e:
        logger.error(f"Error adding interest for user {user.id}: {str(e)}")
        return False


def get_statement_summary(user: User, year: int, month: int) -> Dict[str, Any]:
    """
    Get summary information for a specific statement
    """
    try:
        statement = Statement.objects.get(user=user, year=year, month=month)

        return {
            "reference_code": statement.reference_code,
            "status": statement.status,
            "opening_balance": statement.opening_balance,
            "closing_balance": statement.closing_balance,
            "total_debit": statement.total_debit,
            "total_credit": statement.total_credit,
            "grace_date": statement.grace_date,
            "grace_period_days": statement.get_grace_period_days(),
            "minimum_payment": statement.calculate_minimum_payment_amount(),
            "line_count": statement.lines.count(),
        }

    except Statement.DoesNotExist:
        return {}


def process_user_payment(
        user: User, payment_amount: int, transaction_id: int = None
) -> Dict[str, Any]:
    """
    Process a payment for a user's current statement
    """
    try:
        current_statement = Statement.objects.get_current_statement(user)
        if not current_statement:
            return {"success": False, "error": "No current statement found"}

        # Find pending statements for this user
        pending_statements = Statement.objects.filter(
            user=user, status="pending_payment"
        ).order_by("year", "month")

        if not pending_statements.exists():
            return {"success": False, "error": "No pending statements found"}

        # Apply payment to oldest pending statement
        target_statement = pending_statements.first()

        if not target_statement.is_within_grace():
            return {"success": False, "error": "Grace period has ended"}

        outcome = target_statement.process_payment_during_grace_period(
            payment_amount
        )

        logger.info(
            f"Processed payment for user {user.id}: "
            f"{payment_amount} Rials, outcome: {outcome['status']}"
        )

        return {
            "success": True, "statement_id": target_statement.id,
            "outcome": outcome
        }

    except Exception as e:
        logger.error(f"Error processing payment for user {user.id}: {str(e)}")
        return {"success": False, "error": str(e)}


def get_overdue_statements() -> List[Statement]:
    """
    Get all statements that are overdue for payment
    """
    from django.utils import timezone

    return Statement.objects.filter(
        status="pending_payment", grace_date__lt=timezone.now()
    ).select_related("user")


def calculate_daily_penalties() -> Dict[str, Any]:
    logger.info("Starting daily penalty calculation")
    overdue_candidates = Statement.objects.filter(
        status=StatementStatus.PENDING_PAYMENT, grace_date__lt=timezone.now()
    ).select_related("user")
    processed = 0;
    errors = []
    for st in overdue_candidates:
        try:
            with transaction.atomic():
                if st.calculate_and_apply_penalty() > 0:
                    processed += 1
        except Exception as e:
            errors.append(f"{st.id}: {e}")
    return {"statements_processed": processed, "errors": errors}
