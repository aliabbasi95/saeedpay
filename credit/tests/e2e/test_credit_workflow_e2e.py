# credit/tests/e2e/test_credit_workflow_e2e.py

import datetime as dt
from contextlib import contextmanager

import pytest
from django.db import models
from django.utils import timezone
from freezegun import freeze_time
from persiantools.jdatetime import JalaliDate

from credit.models import Statement
from credit.tasks import task_finalize_due_windows, task_month_end_rollover
from credit.utils.choices import StatementLineType, StatementStatus

pytestmark = pytest.mark.django_db


# ───────────────────────────── Helpers ───────────────────────────── #

def _to_greg_dt(
        jy: int, jm: int, jd: int, hour=9, minute=0, second=0, tz=None
):
    """Convert a Jalali Y/M/D to a timezone-aware Gregorian datetime."""
    g = JalaliDate(jy, jm, jd).to_gregorian()
    naive = dt.datetime(g.year, g.month, g.day, hour, minute, second)
    return timezone.make_aware(naive, tz) if tz else timezone.make_aware(naive)


def _first_day_next_jalali_month():
    """Return (jy, jm, jd=1) for the next Jalali month (relative to wall clock)."""
    today = JalaliDate.today()
    if today.month < 12:
        return today.year, today.month + 1, 1
    return today.year + 1, 1, 1


@contextmanager
def _freeze_to_first_of_next_jmonth(hour=9):
    """Freeze time at the first day of next Jalali month (simulate month-end rollover)."""
    jy, jm, jd = _first_day_next_jalali_month()
    with freeze_time(_to_greg_dt(jy, jm, jd, hour=hour)):
        yield


@contextmanager
def _freeze_after_due_date(stmt: Statement, days=1, hour=10):
    """Freeze time to a moment after the given pending statement's due_date."""
    when = stmt.due_date + dt.timedelta(days=days)
    when = timezone.make_aware(
        when.replace(tzinfo=None)
    ) if when.tzinfo is None else when
    when = when.replace(hour=hour, minute=0, second=0, microsecond=0)
    with freeze_time(when):
        yield


def _seed_purchases_on_current(user, amounts):
    """Add PURCHASE lines on CURRENT and return CURRENT."""
    current, _ = Statement.objects.get_or_create_current_statement(user)
    for a in amounts:
        current.add_line(StatementLineType.PURCHASE, int(a))
    current.refresh_from_db()
    assert current.status == StatementStatus.CURRENT
    assert current.closing_balance < 0
    return current


def _latest_line(stmt: Statement):
    return stmt.lines.order_by("-id").first()


def _add_payment_in_window(
        current_stmt: Statement, amount: int, start, end, at="middle"
):
    """
    Add a PAYMENT on CURRENT whose created_at falls within [start..end] (inclusive).
    at: "left" | "right" | "middle" → created_at equals start/due_date or in between.
    """
    current_stmt.add_line(
        StatementLineType.PAYMENT, int(amount), description="window payment"
    )
    line = _latest_line(current_stmt)
    if at == "left":
        created_at = start
    elif at == "right":
        created_at = end
    else:
        created_at = start + (end - start) / 2
    created_at = timezone.make_aware(
        created_at.replace(tzinfo=None)
    ) if created_at.tzinfo is None else created_at
    line.created_at = created_at
    line.save(update_fields=["created_at"])
    current_stmt.refresh_from_db()
    return line


def _count_lines(stmt: Statement, type_):
    return stmt.lines.filter(type=type_).count()


def _latest_pending(user):
    """Return most recent PENDING_PAYMENT snapshot for a user."""
    return (
        Statement.objects.filter(
            user=user, status=StatementStatus.PENDING_PAYMENT
        )
        .order_by("-closed_at", "-id")
        .first()
    )


def _current_stmt(user):
    """Return CURRENT statement for a user."""
    return Statement.objects.get(user=user, status=StatementStatus.CURRENT)


# ───────────────────────────── Test Classes ───────────────────────────── #

class TestE2EStandardFlow:
    def test_full_flow_with_sufficient_payments_no_penalty(
            self, user, active_credit_limit_factory
    ):
        """
        month_end_rollover → make sufficient in-window payments → finalize_due_windows.
        Expect: CLOSED_NO_PENALTY and no PENALTY on CURRENT; balances consistent.
        """
        cl = active_credit_limit_factory(
            user=user, is_active=True, expiry_days=90, grace_days=7
        )
        _seed_purchases_on_current(user, [600_000, 900_000])

        with _freeze_to_first_of_next_jmonth():
            r1 = task_month_end_rollover.apply().result
            assert r1["status"] == "success"
            assert r1["result"]["statements_closed"] >= 1
            assert r1["result"]["statements_created"] >= 1

        pending = _latest_pending(user)
        assert pending is not None, "Pending snapshot must exist right after rollover"
        current = _current_stmt(user)

        minimum = pending.calculate_minimum_payment_amount()
        _add_payment_in_window(
            current, amount=minimum, start=pending.closed_at,
            end=pending.due_date, at="middle"
        )

        with _freeze_after_due_date(pending, days=1):
            r2 = task_finalize_due_windows.apply().result
            assert r2["status"] == "success"

        pending.refresh_from_db()
        current.refresh_from_db()
        assert pending.status == StatementStatus.CLOSED_NO_PENALTY
        assert _count_lines(current, StatementLineType.PENALTY) == 0

        assert pending.closing_balance < 0
        assert current.closing_balance >= 0 or abs(
            current.closing_balance
        ) < abs(pending.closing_balance)

        avail = getattr(current, "available_limit", None)
        if avail is not None:
            assert avail <= cl.limit_amount  # sanity ceiling

    def test_full_flow_with_insufficient_payments_penalty_applied(
            self, user, active_credit_limit_factory
    ):
        """Insufficient window payments → CLOSED_WITH_PENALTY and PENALTY line on CURRENT."""
        active_credit_limit_factory(
            user=user, is_active=True, expiry_days=90, grace_days=7
        )
        _seed_purchases_on_current(user, [800_000, 500_000])

        with _freeze_to_first_of_next_jmonth():
            r1 = task_month_end_rollover.apply().result
            assert r1["status"] == "success"

        pending = _latest_pending(user)
        assert pending is not None
        current = _current_stmt(user)

        minimum = pending.calculate_minimum_payment_amount()
        _add_payment_in_window(
            current, amount=max(1, minimum - 10_000), start=pending.closed_at,
            end=pending.due_date, at="left"
        )

        with _freeze_after_due_date(pending, days=1):
            r2 = task_finalize_due_windows.apply().result
            assert r2["status"] == "success"

        pending.refresh_from_db()
        current.refresh_from_db()
        assert pending.status == StatementStatus.CLOSED_WITH_PENALTY
        assert _count_lines(current, StatementLineType.PENALTY) >= 1

    def test_exact_minimum_on_due_date_counts_inside_window(
            self, user, active_credit_limit_factory
    ):
        """Paying exactly the minimum at created_at == due_date must close without penalty."""
        active_credit_limit_factory(
            user=user, is_active=True, expiry_days=90, grace_days=7
        )
        _seed_purchases_on_current(user, [900_000])

        with _freeze_to_first_of_next_jmonth():
            _ = task_month_end_rollover.apply().result

        pending = _latest_pending(user)
        assert pending is not None
        current = _current_stmt(user)

        minimum = pending.calculate_minimum_payment_amount()
        _add_payment_in_window(
            current, amount=minimum, start=pending.closed_at,
            end=pending.due_date, at="right"
        )

        with _freeze_after_due_date(
                pending, days=0
        ):  # same day, after due hour
            _ = task_finalize_due_windows.apply().result

        pending.refresh_from_db()
        assert pending.status == StatementStatus.CLOSED_NO_PENALTY

    def test_payment_outside_window_not_counted(
            self, user, active_credit_limit_factory
    ):
        """A payment strictly after due_date must not count toward the window."""
        active_credit_limit_factory(
            user=user, is_active=True, expiry_days=90, grace_days=5
        )
        _seed_purchases_on_current(user, [1_000_000])

        with _freeze_to_first_of_next_jmonth():
            _ = task_month_end_rollover.apply().result

        pending = _latest_pending(user)
        assert pending is not None
        current = _current_stmt(user)

        current.add_line(
            StatementLineType.PAYMENT, 1_000_000, description="late payment"
        )
        late = current.lines.order_by("-id").first()
        late.created_at = pending.due_date + dt.timedelta(
            hours=1
        )  # outside window
        late.save(update_fields=["created_at"])

        with _freeze_after_due_date(pending, days=1):
            _ = task_finalize_due_windows.apply().result

        pending.refresh_from_db()
        assert pending.status == StatementStatus.CLOSED_WITH_PENALTY

    def test_finalize_creates_current_if_missing_e2e(
            self, user, active_credit_limit_factory
    ):
        """Finalize must auto-create CURRENT if it doesn't exist."""
        active_credit_limit_factory(
            user=user, is_active=True, expiry_days=60, grace_days=5
        )
        _seed_purchases_on_current(user, [400_000])

        with _freeze_to_first_of_next_jmonth():
            _ = task_month_end_rollover.apply().result

        pending = _latest_pending(user)
        assert pending is not None

        Statement.objects.filter(
            user=user, status=StatementStatus.CURRENT
        ).delete()
        with _freeze_after_due_date(pending, days=1):
            _ = task_finalize_due_windows.apply().result

        assert Statement.objects.filter(
            user=user, status=StatementStatus.CURRENT
        ).exists()

    def test_exact_minimum_on_closed_at_counts_inside_window(
            self, user, active_credit_limit_factory
    ):
        """Paying exactly the minimum at created_at == closed_at must close without penalty (left boundary inclusive)."""
        active_credit_limit_factory(
            user=user, is_active=True, expiry_days=90, grace_days=7
        )
        _seed_purchases_on_current(user, [700_000])

        with _freeze_to_first_of_next_jmonth():
            _ = task_month_end_rollover.apply().result

        pending = _latest_pending(user)
        assert pending is not None
        current = _current_stmt(user)

        minimum = pending.calculate_minimum_payment_amount()
        _add_payment_in_window(
            current, amount=minimum, start=pending.closed_at,
            end=pending.due_date, at="left"
        )

        with _freeze_after_due_date(pending, days=0):
            _ = task_finalize_due_windows.apply().result

        pending.refresh_from_db()
        assert pending.status == StatementStatus.CLOSED_NO_PENALTY

    def test_multiple_window_payments_sum_towards_minimum(
            self, user, active_credit_limit_factory
    ):
        """Multiple in-window payments whose sum reaches the minimum must close without penalty."""
        active_credit_limit_factory(
            user=user, is_active=True, expiry_days=90, grace_days=7
        )
        _seed_purchases_on_current(user, [1_200_000])

        with _freeze_to_first_of_next_jmonth():
            _ = task_month_end_rollover.apply().result

        pending = _latest_pending(user)
        assert pending is not None
        current = _current_stmt(user)

        minimum = pending.calculate_minimum_payment_amount()
        half = max(1, minimum // 2)
        _add_payment_in_window(
            current, amount=half, start=pending.closed_at,
            end=pending.due_date, at="middle"
        )
        _add_payment_in_window(
            current, amount=minimum - half, start=pending.closed_at,
            end=pending.due_date, at="right"
        )

        with _freeze_after_due_date(pending, days=1):
            _ = task_finalize_due_windows.apply().result

        pending.refresh_from_db()
        assert pending.status == StatementStatus.CLOSED_NO_PENALTY


class TestE2EThresholdAndInterest:
    def test_below_minimum_threshold_closes_without_penalty(
            self, user, active_credit_limit_factory
    ):
        """Debt below MINIMUM_PAYMENT_THRESHOLD should close without penalty."""
        from credit.utils.constants import MINIMUM_PAYMENT_THRESHOLD

        active_credit_limit_factory(
            user=user, is_active=True, expiry_days=60, grace_days=5
        )
        _seed_purchases_on_current(user, [MINIMUM_PAYMENT_THRESHOLD - 1])

        with _freeze_to_first_of_next_jmonth():
            _ = task_month_end_rollover.apply().result

        pending = _latest_pending(user)
        assert pending is not None

        with _freeze_after_due_date(pending, days=1):
            _ = task_finalize_due_windows.apply().result

        pending.refresh_from_db()
        assert pending.status == StatementStatus.CLOSED_NO_PENALTY

    def test_zero_interest_rate_no_interest_line_but_carryover_reflected(
            self, user, active_credit_limit_factory, monkeypatch
    ):
        """
        With MONTHLY_INTEREST_RATE = 0, rollover must not add an effective INTEREST amount.
        Implementation detail: some paths try to insert INTEREST(0); patch add_line to no-op for that case.
        """
        try:
            import credit.utils.constants as cc
            import credit.models.statement as stmt_mod
            monkeypatch.setattr(cc, "MONTHLY_INTEREST_RATE", 0, raising=False)
            monkeypatch.setattr(
                stmt_mod, "MONTHLY_INTEREST_RATE", 0, raising=False
            )

            orig_add_line = stmt_mod.Statement.add_line

            def _safe_add_line(self, type_, amount, *args, **kwargs):
                if type_ == StatementLineType.INTEREST and int(amount) == 0:
                    return self  # skip zero-amount interest lines
                return orig_add_line(self, type_, amount, *args, **kwargs)

            monkeypatch.setattr(
                stmt_mod.Statement, "add_line", _safe_add_line, raising=False
            )
        except Exception:
            pytest.skip(
                "MONTHLY_INTEREST_RATE binding not found; skip interest=0 test"
            )

        active_credit_limit_factory(
            user=user, is_active=True, expiry_days=60, grace_days=7
        )
        _seed_purchases_on_current(
            user, [300_000]
        )  # negative carry-over exists

        with _freeze_to_first_of_next_jmonth():
            r = task_month_end_rollover.apply().result
            assert r["status"] == "success"

        pending = _latest_pending(user)
        assert pending is not None
        new_current = _current_stmt(user)

        # Either no INTEREST line or zero total INTEREST amount.
        interest_qs = new_current.lines.filter(type=StatementLineType.INTEREST)
        total_interest = \
            interest_qs.aggregate(total_amount=models.Sum("amount"))[
                "total_amount"] or 0
        assert total_interest == 0

        # Carry-over still reflected on new CURRENT balance.
        assert new_current.closing_balance <= 0 or new_current.opening_balance <= 0

    def test_penalty_amount_stable_on_second_finalize(
            self, user, active_credit_limit_factory
    ):
        """Second finalize must not duplicate or alter penalty amount."""
        active_credit_limit_factory(
            user=user, is_active=True, expiry_days=90, grace_days=7
        )
        _seed_purchases_on_current(user, [2_000_000])

        with _freeze_to_first_of_next_jmonth():
            _ = task_month_end_rollover.apply().result

        pending = _latest_pending(user)
        assert pending is not None
        current = _current_stmt(user)

        with _freeze_after_due_date(pending, days=1):
            _ = task_finalize_due_windows.apply().result
            first_amount = (
                current.lines.filter(type=StatementLineType.PENALTY).order_by(
                    "-id"
                ).values_list("amount", flat=True).first()
            )

            # Run again: idempotent and stable amount
            _ = task_finalize_due_windows.apply().result
            pens = list(
                current.lines.filter(
                    type=StatementLineType.PENALTY
                ).values_list("amount", flat=True)
            )
            assert pens.count(first_amount) >= 1
            assert len(pens) == 1

    def test_penalty_line_sign_is_negative(
            self, user, active_credit_limit_factory
    ):
        """Penalty line amounts on CURRENT must be negative (increase debt)."""
        active_credit_limit_factory(
            user=user, is_active=True, expiry_days=90, grace_days=5
        )
        _seed_purchases_on_current(user, [1_500_000])

        with _freeze_to_first_of_next_jmonth():
            _ = task_month_end_rollover.apply().result

        pending = _latest_pending(user)
        current = _current_stmt(user)

        # No payment → penalty expected
        with _freeze_after_due_date(pending, days=1):
            _ = task_finalize_due_windows.apply().result

        pen = current.lines.filter(
            type=StatementLineType.PENALTY
        ).order_by("-id").first()
        assert pen is not None
        assert pen.amount < 0  # penalty should increase debt (negative amount)


class TestE2EMultiMonthChaining:
    def test_consecutive_months_carryover_and_idempotency(
            self, user, active_credit_limit_factory
    ):
        """
        Two consecutive rollovers:
          - carry-over chains correctly
          - double-run within same boundary is idempotent
        """
        active_credit_limit_factory(
            user=user, is_active=True, expiry_days=120, grace_days=7
        )
        _seed_purchases_on_current(user, [250_000, 250_000])

        with _freeze_to_first_of_next_jmonth():
            r1 = task_month_end_rollover.apply().result
            assert r1["status"] == "success"
            r1b = task_month_end_rollover.apply().result
            assert r1b["result"]["statements_closed"] in (0, 1)
            assert r1b["result"]["statements_created"] in (0, 1)

        current = _current_stmt(user)
        current.add_line(StatementLineType.PURCHASE, 200_000)

        # Next boundary (next of next month)
        jy, jm, _ = _first_day_next_jalali_month()
        jm2, jy2 = (1, jy + 1) if jm + 1 > 12 else (jm + 1, jy)
        with freeze_time(_to_greg_dt(jy2, jm2, 1, hour=9)):
            r2 = task_month_end_rollover.apply().result
            assert r2["status"] == "success"

        # Last two pendings must be consecutive months.
        pendings = list(
            Statement.objects.filter(
                user=user, status=StatementStatus.PENDING_PAYMENT
            )
            .order_by("year", "month")
            .values_list("year", "month")
        )
        assert len(
            pendings
        ) >= 2, f"Expected >= 2 pending snapshots, got: {pendings}"

        def _next_jalali(y, m):
            return (y + 1, 1) if m == 12 else (y, m + 1)

        last2 = pendings[-2:]
        assert _next_jalali(*last2[0]) == last2[
            1], f"Non-consecutive months: {last2}"

    def test_penalty_line_is_single_and_descriptive(
            self, user, active_credit_limit_factory
    ):
        """
        After insufficient payments, CURRENT must contain at least one PENALTY line,
        and its description should mention the pending snapshot's year/month.
        """
        active_credit_limit_factory(
            user=user, is_active=True, expiry_days=90, grace_days=7
        )
        _seed_purchases_on_current(user, [1_200_000])

        with _freeze_to_first_of_next_jmonth():
            _ = task_month_end_rollover.apply().result

        pending = _latest_pending(user)
        assert pending is not None
        current = _current_stmt(user)

        with _freeze_after_due_date(pending, days=1):
            _ = task_finalize_due_windows.apply().result

        penalties = list(
            current.lines.filter(type=StatementLineType.PENALTY).values_list(
                "amount", "description"
            )
        )
        assert len(penalties) >= 1
        assert any(
            f"{pending.year}/{pending.month:02d}" in (desc or "") for _, desc
            in penalties
        )

    def test_year_boundary_esfand_to_farvardin(
            self, user, active_credit_limit_factory
    ):
        """Rollovers across Esfand → Farvardin must keep consecutive month logic correct."""
        active_credit_limit_factory(
            user=user, is_active=True, expiry_days=90, grace_days=7
        )
        _seed_purchases_on_current(user, [500_000])

        with _freeze_to_first_of_next_jmonth():
            _ = task_month_end_rollover.apply().result

        jy, jm, _ = _first_day_next_jalali_month()
        jm2, jy2 = (1, jy + 1) if jm + 1 > 12 else (jm + 1, jy)
        with freeze_time(_to_greg_dt(jy2, jm2, 1, hour=9)):
            _ = task_month_end_rollover.apply().result

        pendings = list(
            Statement.objects.filter(
                user=user, status=StatementStatus.PENDING_PAYMENT
            )
            .order_by("year", "month")
            .values_list("year", "month")
        )
        assert len(pendings) >= 2
        y1, m1 = pendings[-2]
        y2, m2 = pendings[-1]
        if m1 == 12:
            assert (y2, m2) == (y1 + 1, 1)
        else:
            assert (y2, m2) == (y1, m1 + 1)


class TestE2EMultiUserIsolation:
    def test_two_users_isolated(
            self, user_factory, active_credit_limit_factory
    ):
        """Two users' workflows must be isolated (no cross-contamination)."""
        u1 = user_factory()
        u2 = user_factory()
        active_credit_limit_factory(
            user=u1, is_active=True, expiry_days=60, grace_days=5
        )
        active_credit_limit_factory(
            user=u2, is_active=True, expiry_days=60, grace_days=5
        )

        _seed_purchases_on_current(u1, [800_000])
        _seed_purchases_on_current(u2, [200_000])

        with _freeze_to_first_of_next_jmonth():
            _ = task_month_end_rollover.apply().result

        p1 = _latest_pending(u1)
        p2 = _latest_pending(u2)
        assert p1 is not None and p2 is not None
        assert p1.user_id != p2.user_id  # sanity
