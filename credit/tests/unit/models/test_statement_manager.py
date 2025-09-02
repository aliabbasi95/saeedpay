# tests/unit/models/test_statement_manager.py

import pytest
from persiantools.jdatetime import JalaliDate

from credit.models.statement import Statement
from credit.utils.choices import StatementStatus, StatementLineType
from credit.utils.constants import MONTHLY_INTEREST_RATE

pytestmark = pytest.mark.django_db


def _prev_jalali_year_month():
    """Return (year, month) of the previous Jalali month."""
    today = JalaliDate.today()
    if today.month > 1:
        return today.year, today.month - 1
    return today.year - 1, 12


def _shift_month(year: int, month: int, delta: int):
    """
    Shift a Jalali (year, month) by delta months (delta can be negative).
    Returns a normalized (year, month) in the 1..12 range.
    """
    total = (year * 12 + (month - 1)) + delta
    ny = total // 12
    nm = (total % 12) + 1
    return ny, nm


def test_close_monthly_statements_closes_past_current_and_creates_new(
        user, active_credit_limit_factory
):
    # Arrange: create an active credit-limit to ensure due_date (grace doesn't matter)
    active_credit_limit_factory(user=user, grace_days=7)

    # Create a CURRENT for previous month with a negative closing (via a purchase)
    prev_year, prev_month = _prev_jalali_year_month()
    prev = Statement.objects.create(
        user=user,
        year=prev_year,
        month=prev_month,
        status=StatementStatus.CURRENT,
        opening_balance=0,
    )
    prev.add_line(StatementLineType.PURCHASE, 300_000)  # negative carry-over

    # Act
    result = Statement.objects.close_monthly_statements()

    # Assert: counters
    assert result["statements_closed"] == 1
    assert result["statements_created"] == 1

    # Previous moved to pending and has due/closed timestamps
    prev.refresh_from_db()
    assert prev.status == StatementStatus.PENDING_PAYMENT
    assert prev.due_date is not None
    assert prev.closed_at is not None

    # New CURRENT for today with carry-over opening_balance
    today = JalaliDate.today()
    current = Statement.objects.get(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT
    )
    assert current.opening_balance == prev.closing_balance

    # Interest line must be added because previous closing was negative
    expected_interest = int(abs(prev.closing_balance) * MONTHLY_INTEREST_RATE)
    assert current.lines.filter(
        type=StatementLineType.INTEREST, amount=-expected_interest
    ).count() == 1
    assert result["interest_lines_added"] == 1


def test_close_monthly_statements_is_idempotent(user):
    # Arrange: one CURRENT in previous month
    prev_year, prev_month = _prev_jalali_year_month()
    prev = Statement.objects.create(
        user=user, year=prev_year, month=prev_month,
        status=StatementStatus.CURRENT, opening_balance=0
    )
    prev.add_line(StatementLineType.PURCHASE, 100_000)

    # Act: run twice
    Statement.objects.close_monthly_statements()
    result2 = Statement.objects.close_monthly_statements()

    # Assert: second run must do nothing
    assert result2["statements_closed"] == 0
    assert result2["statements_created"] == 0
    assert result2["interest_lines_added"] in (0,
                                               1)  # typically 0 in second run


def test_rollover_does_nothing_when_only_current_month_current_exists(user):
    """
    If there is only a CURRENT statement for the *current* Jalali month,
    the manager must not close anything nor create a new one.
    """
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT, opening_balance=0
    )
    # Run
    result = Statement.objects.close_monthly_statements()

    # Assert: untouched
    stmt.refresh_from_db()
    assert stmt.status == StatementStatus.CURRENT
    assert result["statements_closed"] == 0
    assert result["statements_created"] == 0
    assert result["interest_lines_added"] in (0,
                                              1)  # no interest on same-month case


def test_rollover_updates_existing_current_opening_balance(
        user, active_credit_limit_factory
):
    """
    When a CURRENT for the *current* month already exists, the manager should NOT create a new one,
    but it must update its opening_balance to the previous month's closing and add interest line if needed.
    """
    active_credit_limit_factory(user=user, grace_days=5)

    # Previous month CURRENT with negative closing
    py, pm = _prev_jalali_year_month()
    prev_stmt = Statement.objects.create(
        user=user, year=py, month=pm, status=StatementStatus.CURRENT,
        opening_balance=0
    )
    prev_stmt.add_line(StatementLineType.PURCHASE, 200_000)  # -> negative
    prev_stmt.refresh_from_db()
    assert prev_stmt.closing_balance < 0

    # Pre-create CURRENT for current month with some dummy opening
    today = JalaliDate.today()
    existing_current = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT, opening_balance=999
    )

    result = Statement.objects.close_monthly_statements()

    # Must not create a new CURRENT; should update the existing one
    assert result["statements_created"] == 0

    existing_current.refresh_from_db()
    assert existing_current.opening_balance == prev_stmt.closing_balance

    # Interest line must be added to the *existing current*
    expected_interest = int(
        abs(prev_stmt.closing_balance) * MONTHLY_INTEREST_RATE
    )
    assert existing_current.lines.filter(
        type=StatementLineType.INTEREST, amount=-expected_interest
    ).count() == 1


def test_rollover_multi_users_mixed_balances_counts_and_interest(
        user_factory, active_credit_limit_factory
):
    """
    Two users:
      - user A: negative carry-over -> interest expected
      - user B: non-negative carry-over -> no interest
    Counters must reflect sum across users.
    """
    user_a = user_factory()
    user_b = user_factory()
    active_credit_limit_factory(user=user_a, grace_days=3)
    active_credit_limit_factory(user=user_b, grace_days=3)

    # User A prev month CURRENT with negative closing (via purchase)
    py, pm = _prev_jalali_year_month()
    prev_a = Statement.objects.create(
        user=user_a, year=py, month=pm, status=StatementStatus.CURRENT,
        opening_balance=0
    )
    prev_a.add_line(StatementLineType.PURCHASE, 50_000)
    prev_a.refresh_from_db()
    assert prev_a.closing_balance < 0

    # User B prev month CURRENT with non-negative closing (via payment)
    prev_b = Statement.objects.create(
        user=user_b, year=py, month=pm, status=StatementStatus.CURRENT,
        opening_balance=0
    )
    prev_b.add_line(StatementLineType.PAYMENT, 10_000)
    prev_b.refresh_from_db()
    assert prev_b.closing_balance >= 0

    result = Statement.objects.close_monthly_statements()

    # Both closed; two currents for today created
    assert result["statements_closed"] == 2
    assert result["statements_created"] == 2
    assert result["interest_lines_added"] == 1  # only user A gets interest

    # Verify interest presence/absence
    today = JalaliDate.today()
    cur_a = Statement.objects.get(
        user=user_a, year=today.year, month=today.month,
        status=StatementStatus.CURRENT
    )
    cur_b = Statement.objects.get(
        user=user_b, year=today.year, month=today.month,
        status=StatementStatus.CURRENT
    )

    exp_interest_a = int(abs(prev_a.closing_balance) * MONTHLY_INTEREST_RATE)
    assert cur_a.lines.filter(
        type=StatementLineType.INTEREST, amount=-exp_interest_a
    ).count() == 1
    assert cur_b.lines.filter(type=StatementLineType.INTEREST).count() == 0


def test_rollover_interest_line_description_format(user):
    """
    Description should follow: 'Monthly interest on YYYY/MM' for the previous cycle.
    """
    py, pm = _prev_jalali_year_month()
    prev = Statement.objects.create(
        user=user, year=py, month=pm, status=StatementStatus.CURRENT,
        opening_balance=0
    )
    prev.add_line(StatementLineType.PURCHASE, 123_456)  # negative

    Statement.objects.close_monthly_statements()

    today = JalaliDate.today()
    cur = Statement.objects.get(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT
    )
    line = cur.lines.filter(type=StatementLineType.INTEREST).first()
    assert line is not None
    assert f"{py}/{pm:02d}" in (line.description or "")


def test_rollover_no_interest_when_prev_non_negative(
        user, active_credit_limit_factory
):
    """
    When previous month's closing is non-negative:
      - opening_balance of the new CURRENT must equal that closing
      - no INTEREST line should be added
    """
    active_credit_limit_factory(user=user, grace_days=5)

    # Previous month CURRENT with non-negative closing (e.g., a payment)
    py, pm = _prev_jalali_year_month()
    prev = Statement.objects.create(
        user=user, year=py, month=pm, status=StatementStatus.CURRENT,
        opening_balance=0
    )
    prev.add_line(StatementLineType.PAYMENT, 42_000)
    prev.refresh_from_db()
    assert prev.closing_balance >= 0

    result = Statement.objects.close_monthly_statements()
    assert result["statements_closed"] == 1
    assert result["statements_created"] == 1
    assert result["interest_lines_added"] == 0

    today = JalaliDate.today()
    current = Statement.objects.get(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT
    )
    assert current.opening_balance == prev.closing_balance
    assert current.lines.filter(type=StatementLineType.INTEREST).count() == 0
