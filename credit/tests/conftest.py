# credit/tests/conftest.py

import contextlib
from datetime import timedelta
from typing import Callable, Tuple, Optional

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from persiantools.jdatetime import JalaliDate

from credit.models.credit_limit import CreditLimit
from credit.models.statement import Statement
from credit.utils.choices import StatementStatus, StatementLineType

User = get_user_model()


@pytest.fixture
def user_factory(db):
    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        username = kwargs.pop("username", f"user_{counter['i']}")
        return User.objects.create(
            username=username, password="test", **kwargs
        )

    return _make


@pytest.fixture
def user(db, user_factory):
    return user_factory()


@pytest.fixture
def active_credit_limit_factory(db):
    def _make(
            user,
            approved_limit=5_000_000,
            is_active=True,
            grace_days=None,
            expiry_days=365,
            *,
            expiry_date=None,
    ):
        """
        Create a CreditLimit. If expiry_date is provided, it wins.
        Otherwise expiry_date = today + expiry_days.
        """
        exp_date = expiry_date or (
                timezone.localdate() + timedelta(days=expiry_days))
        obj = CreditLimit.objects.create(
            user=user,
            approved_limit=approved_limit,
            is_active=is_active,
            grace_period_days=grace_days,
            expiry_date=exp_date,
        )
        return obj

    return _make


@pytest.fixture
def current_statement_factory(db):
    def _make(user, opening_balance=0):
        today_j = JalaliDate.today()
        stmt, created = Statement.objects.get_or_create(
            user=user,
            year=today_j.year,
            month=today_j.month,
            defaults={
                "status": StatementStatus.CURRENT,
                "opening_balance": opening_balance
            },
        )
        if not created and stmt.status != StatementStatus.CURRENT:
            stmt.status = StatementStatus.CURRENT
            stmt.opening_balance = opening_balance
            stmt.save(update_fields=["status", "opening_balance"])
        stmt.update_balances()
        return stmt

    return _make


# ──────────────────────────────────────────────────────────────────────────────
# Extra testing utilities (safe to append; no breaking changes)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def celery_eager(settings):
    """
    Run Celery tasks synchronously/eager during tests.
    Also propagate exceptions immediately and avoid noisy retries.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    # Some projects use CELERY_TASK_IGNORE_RESULT; keep defaults if absent
    yield


@pytest.fixture
def jalali_helpers():
    """
    Small helpers for Jalali month arithmetic used across tests.
    Returns two callables: prev_month() and shift_month(y, m, delta).
    """

    def prev_month() -> Tuple[int, int]:
        today = JalaliDate.today()
        if today.month > 1:
            return today.year, today.month - 1
        return today.year - 1, 12

    def shift_month(year: int, month: int, delta: int) -> Tuple[int, int]:
        total = (year * 12 + (month - 1)) + delta
        ny = total // 12
        nm = (total % 12) + 1
        return ny, nm

    return type(
        "JalaliHelpers", (),
        {"prev_month": prev_month, "shift_month": shift_month}
    )


@pytest.fixture
def statement_factory(db) -> Callable[..., Statement]:
    """
    Generic Statement factory with sensible defaults.
    Example:
      stmt = statement_factory(user=user, status=StatementStatus.CURRENT, opening_balance=0)
    """

    def _make(
            *,
            user,
            status: StatementStatus = StatementStatus.CURRENT,
            year: Optional[int] = None,
            month: Optional[int] = None,
            opening_balance: int = 0,
            due_date=None,
            closed_at=None,
            total_debit: int = 0,
            total_credit: int = 0,
            closing_balance: Optional[int] = None,
    ) -> Statement:
        today_j = JalaliDate.today()
        y = year if year is not None else today_j.year
        m = month if month is not None else today_j.month

        stmt = Statement.objects.create(
            user=user,
            year=y,
            month=m,
            status=status,
            opening_balance=opening_balance,
            due_date=due_date,
            closed_at=closed_at,
            total_debit=total_debit,
            total_credit=total_credit,
            # If closing not provided, let model compute it via update_balances()
            closing_balance=closing_balance if closing_balance is not None else 0,
        )
        # keep balances consistent
        stmt.update_balances()
        return stmt

    return _make


@pytest.fixture
def pending_past_due_statement_factory(db, jalali_helpers, statement_factory):
    """
    Create a PENDING_PAYMENT statement on the previous Jalali month whose due_date is already past.
    Useful for finalize_due_windows and penalty/closure scenarios.
    """

    def _make(
            *,
            user,
            debt: int = 300_000,
            days_past_due: int = 5,
            days_since_closed: int = 10,
    ) -> Statement:
        py, pm = jalali_helpers.prev_month()
        now = timezone.now()

        stmt = statement_factory(
            user=user,
            status=StatementStatus.PENDING_PAYMENT,
            year=py,
            month=pm,
            opening_balance=0,
            due_date=now - timedelta(days=days_past_due),
            closed_at=now - timedelta(days=days_since_closed),
        )
        # Ensure negative closing (debt)
        if stmt.closing_balance >= 0:
            stmt.add_line(StatementLineType.PURCHASE, abs(debt))
            stmt.refresh_from_db()
        return stmt

    return _make


@contextlib.contextmanager
def _isolate_user_statements(user):
    """
    Context manager: temporarily remove user's statements inside the block
    and restore nothing (used only for tests that want a blank slate).
    It is intentionally simple because tests run in a DB transaction anyway.
    """
    Statement.objects.filter(user=user).delete()
    try:
        yield
    finally:
        # No automatic restoration; tests should create what they need explicitly.
        pass


@pytest.fixture
def isolate_user_statements():
    """
    Yield a callable that returns a context manager to clear a user's statements.
    Usage:
        with isolate_user_statements()(user):
            # create from scratch...
            Statement.objects.get_or_create_current_statement(user)
    """

    def _wrap(user):
        return _isolate_user_statements(user)

    return _wrap
