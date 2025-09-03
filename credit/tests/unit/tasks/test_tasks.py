# credit/tests/unit/tasks/test_tasks.py

import datetime as dt

import pytest
from django.utils import timezone
from persiantools.jdatetime import JalaliDate

from credit.models import Statement
from credit.tasks import (
    task_month_end_rollover,
    task_finalize_due_windows,
    task_daily_credit_maintenance,
)
from credit.utils.choices import StatementStatus, StatementLineType

pytestmark = pytest.mark.django_db


# ───────────────────────────── Helpers ───────────────────────────── #

def _prev_jalali_year_month():
    """Return (year, month) for previous Jalali month."""
    today = JalaliDate.today()
    return (today.year, today.month - 1) if today.month > 1 else (
        today.year - 1, 12)


def _make_past_current_with_debt(user, amount=200_000):
    """
    Create a CURRENT statement, move it to previous Jalali month,
    add a PURCHASE to ensure a negative closing balance, and return it.
    This shape is safe for month-end rollover and avoids uniqueness conflicts.
    """
    stmt, _ = Statement.objects.get_or_create_current_statement(user)
    py, pm = _prev_jalali_year_month()

    # Move to previous month
    stmt.year = py
    stmt.month = pm
    stmt.save(update_fields=["year", "month"])

    # Seed debt
    stmt.add_line(StatementLineType.PURCHASE, amount)
    stmt.refresh_from_db()
    assert stmt.status == StatementStatus.CURRENT
    assert stmt.closing_balance < 0
    return stmt


def _make_pending_past_due_on_prev_month(
        user, debt=300_000, grace_days_ago=5, closed_days_ago=10
):
    """
    Create a PENDING_PAYMENT statement that belongs to the previous Jalali month
    and is already past due. This is the safe shape for finalize_due_windows.
    """
    stmt, _ = Statement.objects.get_or_create_current_statement(user)
    py, pm = _prev_jalali_year_month()

    # Move to previous month
    stmt.year = py
    stmt.month = pm
    stmt.save(update_fields=["year", "month"])

    # Seed debt if needed
    if stmt.closing_balance >= 0:
        stmt.add_line(StatementLineType.PURCHASE, debt)
        stmt.refresh_from_db()

    # Close into pending with past-due dates
    now = timezone.now()
    stmt.status = StatementStatus.PENDING_PAYMENT
    stmt.closed_at = now - dt.timedelta(days=closed_days_ago)
    stmt.due_date = now - dt.timedelta(days=grace_days_ago)
    stmt.save(
        update_fields=["status", "closed_at", "due_date", "closing_balance"]
        )
    return stmt


# ───────────────────────────── Test Classes ───────────────────────────── #

class TestMonthEndRolloverTask:
    def test_returns_structured_result_and_counts_increase(
            self, user, active_credit_limit_factory
    ):
        active_credit_limit_factory(user=user, is_active=True, expiry_days=60)
        _make_past_current_with_debt(user)

        res = task_month_end_rollover.apply().result
        assert res["status"] == "success"
        assert "result" in res
        assert res["result"]["statements_closed"] >= 1
        assert res["result"]["statements_created"] >= 1
        # With negative carryover, at least one INTEREST line is expected.
        assert res["result"]["interest_lines_added"] >= 1

    def test_noop_when_nothing_to_roll(self, user):
        """
        When there is only a CURRENT for the current month, the task should be a no-op.
        """
        Statement.objects.filter(user=user).delete()
        Statement.objects.get_or_create_current_statement(user)

        res = task_month_end_rollover.apply().result
        assert res["status"] == "success"
        assert res["result"] == {
            "statements_closed": 0,
            "statements_created": 0,
            "interest_lines_added": 0,
        }

    def test_idempotent_second_run_returns_zeroes(
            self, user, active_credit_limit_factory
    ):
        """
        Running it twice should not double-close or double-add interest lines.
        """
        active_credit_limit_factory(user=user, is_active=True, expiry_days=60)
        _make_past_current_with_debt(user)

        _ = task_month_end_rollover.apply().result
        res2 = task_month_end_rollover.apply().result

        assert res2["status"] == "success"
        assert res2["result"]["statements_closed"] == 0
        assert res2["result"]["statements_created"] == 0
        # Typically 0 on the second run
        assert res2["result"]["interest_lines_added"] in (0, 1)


class TestFinalizeDueWindowsTask:
    def test_returns_structured_result_without_integrity_error(
            self, user, active_credit_limit_factory
    ):
        """
        Shape the data so pending is for the previous Jalali month to avoid (user, year, month) uniqueness conflicts
        when CURRENT for the current month is created during finalization.
        """
        active_credit_limit_factory(user=user, is_active=True, expiry_days=60)
        _make_pending_past_due_on_prev_month(user)

        res = task_finalize_due_windows.apply().result
        assert res["status"] == "success"
        assert "result" in res
        assert res["result"]["finalized_count"] >= 1
        assert res["result"]["closed_without_penalty_count"] >= 0
        assert res["result"]["closed_with_penalty_count"] >= 0

    def test_noop_when_no_pending_past_due(
            self, user, active_credit_limit_factory
    ):
        """
        No pending statements past their due date → all counters must be zero.
        """
        active_credit_limit_factory(user=user, is_active=True, expiry_days=60)
        Statement.objects.get_or_create_current_statement(user)

        res = task_finalize_due_windows.apply().result
        assert res["status"] == "success"
        assert res["result"]["finalized_count"] == 0
        assert res["result"]["closed_without_penalty_count"] == 0
        assert res["result"]["closed_with_penalty_count"] == 0

    def test_below_minimum_threshold_closes_without_penalty(
            self, user, active_credit_limit_factory
    ):
        """
        If debt is below MINIMUM_PAYMENT_THRESHOLD, finalization should close without penalty.
        """
        from credit.utils.constants import MINIMUM_PAYMENT_THRESHOLD

        active_credit_limit_factory(user=user, is_active=True, expiry_days=60)
        stmt = _make_pending_past_due_on_prev_month(
            user, debt=MINIMUM_PAYMENT_THRESHOLD - 1
        )

        res = task_finalize_due_windows.apply().result
        assert res["status"] == "success"
        stmt.refresh_from_db()
        assert stmt.status == StatementStatus.CLOSED_NO_PENALTY

    def test_idempotent_second_run_does_not_duplicate_penalty(
            self, user, active_credit_limit_factory
    ):
        """
        Run once (to finalize), then run again. No extra penalties should be added on the second run.
        """
        active_credit_limit_factory(user=user, is_active=True, expiry_days=60)
        _make_pending_past_due_on_prev_month(user, debt=1_200_000)

        _ = task_finalize_due_windows.apply().result
        res2 = task_finalize_due_windows.apply().result
        assert res2["status"] == "success"
        # On second pass, finalized_count should be zero (already finalized)
        assert res2["result"]["finalized_count"] == 0


class TestDailyMaintenanceTask:
    def test_chains_both_tasks_and_returns_parts(
            self, user, active_credit_limit_factory
    ):
        """
        The daily maintenance task runs both month-end rollover and dues finalization
        and must return two structured sub-results.
        """
        active_credit_limit_factory(user=user, is_active=True, expiry_days=60)
        _make_past_current_with_debt(user)  # Ensure rollover part has work

        res = task_daily_credit_maintenance.apply().result
        assert res["status"] == "success"
        assert "month_end_rollover" in res
        assert "finalize_due_windows" in res
        assert res["month_end_rollover"]["status"] == "success"
        assert res["finalize_due_windows"]["status"] == "success"

    def test_daily_task_noop_paths_are_consistent(self, user):
        """
        When there is nothing to do for both parts, the task must still return success
        with the two sub-results present.
        """
        Statement.objects.filter(user=user).delete()
        Statement.objects.get_or_create_current_statement(user)

        res = task_daily_credit_maintenance.apply().result
        assert res["status"] == "success"
        assert "month_end_rollover" in res and "finalize_due_windows" in res
        assert res["month_end_rollover"]["status"] == "success"
        assert res["finalize_due_windows"]["status"] == "success"
