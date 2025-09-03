import pytest
from persiantools.jdatetime import JalaliDate

from credit.models.statement import Statement
from credit.utils.choices import StatementStatus, StatementLineType
from credit.utils.constants import MONTHLY_INTEREST_RATE

pytestmark = pytest.mark.django_db


# ───────────────────────────── Helpers ───────────────────────────── #

def _prev_jalali_year_month():
    """Return (year, month) of the previous Jalali month."""
    today = JalaliDate.today()
    return (today.year, today.month - 1) if today.month > 1 else (
        today.year - 1, 12)


def _shift_month(year: int, month: int, delta: int):
    """Shift a Jalali (year, month) by delta months; return normalized (year, month)."""
    total = (year * 12 + (month - 1)) + delta
    return total // 12, (total % 12) + 1


# ───────────────────────────── Tests ───────────────────────────── #

class TestCloseMonthlyStatements:
    def test_closes_past_current_and_creates_new(
            self, user, active_credit_limit_factory
    ):
        active_credit_limit_factory(user=user, grace_days=7)
        py, pm = _prev_jalali_year_month()
        prev = Statement.objects.create(
            user=user, year=py, month=pm, status=StatementStatus.CURRENT,
            opening_balance=0
        )
        prev.add_line(
            StatementLineType.PURCHASE, 300_000
        )  # negative carry-over

        result = Statement.objects.close_monthly_statements()

        assert result["statements_closed"] == 1
        assert result["statements_created"] == 1

        prev.refresh_from_db()
        assert prev.status == StatementStatus.PENDING_PAYMENT
        assert prev.due_date is not None and prev.closed_at is not None

        today = JalaliDate.today()
        current = Statement.objects.get(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        assert current.opening_balance == prev.closing_balance

        expected_interest = int(
            abs(prev.closing_balance) * MONTHLY_INTEREST_RATE
        )
        assert current.lines.filter(
            type=StatementLineType.INTEREST, amount=-expected_interest
        ).count() == 1
        assert result["interest_lines_added"] == 1

    def test_is_idempotent(self, user):
        py, pm = _prev_jalali_year_month()
        prev = Statement.objects.create(
            user=user, year=py, month=pm, status=StatementStatus.CURRENT,
            opening_balance=0
        )
        prev.add_line(StatementLineType.PURCHASE, 100_000)

        Statement.objects.close_monthly_statements()
        result2 = Statement.objects.close_monthly_statements()

        assert result2["statements_closed"] == 0
        assert result2["statements_created"] == 0
        assert result2["interest_lines_added"] in (0,
                                                   1)  # typically 0 on rerun

    def test_noop_when_only_current_month_current_exists(self, user):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT, opening_balance=0
        )
        result = Statement.objects.close_monthly_statements()
        stmt.refresh_from_db()
        assert stmt.status == StatementStatus.CURRENT
        assert result["statements_closed"] == 0
        assert result["statements_created"] == 0
        assert result["interest_lines_added"] in (0, 1)

    def test_updates_existing_current_opening_balance(
            self, user, active_credit_limit_factory
    ):
        active_credit_limit_factory(user=user, grace_days=5)
        py, pm = _prev_jalali_year_month()
        prev_stmt = Statement.objects.create(
            user=user, year=py, month=pm, status=StatementStatus.CURRENT,
            opening_balance=0
        )
        prev_stmt.add_line(StatementLineType.PURCHASE, 200_000)
        prev_stmt.refresh_from_db()
        assert prev_stmt.closing_balance < 0

        today = JalaliDate.today()
        existing_current = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT, opening_balance=999
        )

        result = Statement.objects.close_monthly_statements()
        assert result["statements_created"] == 0

        existing_current.refresh_from_db()
        assert existing_current.opening_balance == prev_stmt.closing_balance

        expected_interest = int(
            abs(prev_stmt.closing_balance) * MONTHLY_INTEREST_RATE
        )
        assert existing_current.lines.filter(
            type=StatementLineType.INTEREST, amount=-expected_interest
        ).count() == 1

    def test_multi_users_mixed_balances_counts_and_interest(
            self, user_factory, active_credit_limit_factory
    ):
        user_a = user_factory()
        user_b = user_factory()
        active_credit_limit_factory(user=user_a, grace_days=3)
        active_credit_limit_factory(user=user_b, grace_days=3)

        py, pm = _prev_jalali_year_month()
        prev_a = Statement.objects.create(
            user=user_a, year=py, month=pm, status=StatementStatus.CURRENT,
            opening_balance=0
        )
        prev_a.add_line(StatementLineType.PURCHASE, 50_000)
        prev_a.refresh_from_db()
        assert prev_a.closing_balance < 0

        prev_b = Statement.objects.create(
            user=user_b, year=py, month=pm, status=StatementStatus.CURRENT,
            opening_balance=0
        )
        prev_b.add_line(StatementLineType.PAYMENT, 10_000)
        prev_b.refresh_from_db()
        assert prev_b.closing_balance >= 0

        result = Statement.objects.close_monthly_statements()
        assert result["statements_closed"] == 2
        assert result["statements_created"] == 2
        assert result["interest_lines_added"] == 1

        today = JalaliDate.today()
        cur_a = Statement.objects.get(
            user=user_a, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        cur_b = Statement.objects.get(
            user=user_b, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        exp_interest_a = int(
            abs(prev_a.closing_balance) * MONTHLY_INTEREST_RATE
        )
        assert cur_a.lines.filter(
            type=StatementLineType.INTEREST, amount=-exp_interest_a
        ).count() == 1
        assert cur_b.lines.filter(type=StatementLineType.INTEREST).count() == 0

    def test_interest_line_description_format(self, user):
        py, pm = _prev_jalali_year_month()
        prev = Statement.objects.create(
            user=user, year=py, month=pm, status=StatementStatus.CURRENT,
            opening_balance=0
        )
        prev.add_line(StatementLineType.PURCHASE, 123_456)
        Statement.objects.close_monthly_statements()

        today = JalaliDate.today()
        cur = Statement.objects.get(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        line = cur.lines.filter(type=StatementLineType.INTEREST).first()
        assert line is not None and f"{py}/{pm:02d}" in (
                line.description or "")

    def test_no_interest_when_prev_non_negative(
            self, user, active_credit_limit_factory
    ):
        active_credit_limit_factory(user=user, grace_days=5)
        py, pm = _prev_jalali_year_month()
        prev = Statement.objects.create(
            user=user, year=py, month=pm, status=StatementStatus.CURRENT,
            opening_balance=0
        )
        prev.add_line(StatementLineType.PAYMENT, 42_000)
        prev.refresh_from_db()
        assert prev.closing_balance >= 0

        res = Statement.objects.close_monthly_statements()
        assert res["statements_closed"] == 1 and res[
            "statements_created"] == 1 and res["interest_lines_added"] == 0
        today = JalaliDate.today()
        current = Statement.objects.get(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        assert current.opening_balance == prev.closing_balance
        assert current.lines.filter(
            type=StatementLineType.INTEREST
        ).count() == 0

    def test_no_interest_when_prev_closing_exact_zero(
            self, user, active_credit_limit_factory
    ):
        active_credit_limit_factory(user=user, grace_days=5)
        py, pm = _prev_jalali_year_month()
        prev = Statement.objects.create(
            user=user, year=py, month=pm, status=StatementStatus.CURRENT,
            opening_balance=0
        )
        prev.refresh_from_db()
        assert prev.closing_balance == 0

        res = Statement.objects.close_monthly_statements()
        assert res["statements_closed"] == 1 and res[
            "statements_created"] == 1 and res["interest_lines_added"] == 0
        today = JalaliDate.today()
        cur = Statement.objects.get(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        assert cur.opening_balance == 0
        assert cur.lines.filter(type=StatementLineType.INTEREST).count() == 0

    def test_existing_current_does_not_duplicate_interest(
            self, user, active_credit_limit_factory
    ):
        active_credit_limit_factory(user=user, grace_days=5)
        py, pm = _prev_jalali_year_month()
        prev = Statement.objects.create(
            user=user, year=py, month=pm, status=StatementStatus.CURRENT,
            opening_balance=0
        )
        prev.add_line(StatementLineType.PURCHASE, 120_000)
        prev.refresh_from_db()
        assert prev.closing_balance < 0

        today = JalaliDate.today()
        cur = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT, opening_balance=999
        )

        Statement.objects.close_monthly_statements()
        cur.refresh_from_db()
        first_count = cur.lines.filter(type=StatementLineType.INTEREST).count()
        assert first_count == 1

        Statement.objects.close_monthly_statements()
        cur.refresh_from_db()
        second_count = cur.lines.filter(
            type=StatementLineType.INTEREST
        ).count()
        assert second_count == 1  # no duplication

    def test_without_credit_limit_sets_due_immediately(self, user):
        py, pm = _prev_jalali_year_month()
        prev = Statement.objects.create(
            user=user, year=py, month=pm, status=StatementStatus.CURRENT,
            opening_balance=0
        )
        prev.add_line(StatementLineType.PURCHASE, 10_000)
        Statement.objects.close_monthly_statements()
        prev.refresh_from_db()
        assert prev.status == StatementStatus.PENDING_PAYMENT
        assert prev.closed_at is not None and prev.due_date is not None
        assert (prev.due_date - prev.closed_at).days == 0
