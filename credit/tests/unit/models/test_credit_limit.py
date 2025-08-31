# credit/tests/unit/models/test_credit_limit.py

import pytest
from django.db import IntegrityError
from django.utils import timezone
from persiantools.jdatetime import JalaliDate

from credit.models.credit_limit import CreditLimit
from credit.models.statement import Statement
from credit.utils.choices import StatementLineType, StatementStatus


pytestmark = pytest.mark.django_db


# ---------- Helpers ----------

def _prev_jalali_year_month():
    """Return (year, month) for previous Jalali month."""
    today = JalaliDate.today()
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


# ---------- Manager: get_user_credit_limit ----------

def test_get_user_credit_limit_returns_active_non_expired(user, active_credit_limit_factory):
    limit = active_credit_limit_factory(user=user, is_active=True, expiry_date=timezone.localdate() + timezone.timedelta(days=1))
    got = CreditLimit.objects.get_user_credit_limit(user)
    assert got == limit


def test_get_user_credit_limit_ignores_expired(user, active_credit_limit_factory):
    # Only expired active limit exists => manager should return None
    active_credit_limit_factory(user=user, is_active=True, expiry_date=timezone.localdate() - timezone.timedelta(days=1))
    assert CreditLimit.objects.get_user_credit_limit(user) is None


# ---------- Manager: get_available_credit ----------

def test_get_available_credit_no_limit_returns_zero(user):
    assert CreditLimit.objects.get_available_credit(user) == 0


def test_get_available_credit_matches_property(user, active_credit_limit_factory, current_statement_factory):
    limit = active_credit_limit_factory(user=user, approved_limit=1_000_000, is_active=True, expiry_date=timezone.localdate() + timezone.timedelta(days=10))
    stmt = current_statement_factory(user=user, opening_balance=0)
    # One purchase of 150,000 (debit) on CURRENT
    stmt.add_line(StatementLineType.PURCHASE, 150_000)
    stmt.refresh_from_db()

    assert CreditLimit.objects.get_available_credit(user) == limit.available_limit == 850_000


# ---------- available_limit behavior ----------

def test_available_limit_uses_only_current_debt_ignores_pending(user, active_credit_limit_factory):
    limit = active_credit_limit_factory(user=user, approved_limit=500_000, is_active=True, expiry_date=timezone.localdate() + timezone.timedelta(days=5))

    # Create a PENDING statement with a negative closing balance (older month).
    y, m = _prev_jalali_year_month()
    Statement.objects.create(
        user=user,
        year=y,
        month=m,
        status=StatementStatus.PENDING_PAYMENT,
        opening_balance=0,
        closing_balance=-400_000,
        total_debit=400_000,
        total_credit=0,
        due_date=timezone.now() + timezone.timedelta(days=3),
    )

    # No CURRENT debt exists => available_limit should equal approved_limit
    assert limit.available_limit == 500_000


def test_available_limit_is_clamped_to_zero_when_carryover_exceeds_limit(user, active_credit_limit_factory, current_statement_factory):
    limit = active_credit_limit_factory(user=user, approved_limit=100_000, is_active=True, expiry_date=timezone.localdate() + timezone.timedelta(days=5))

    # Simulate a current carryover debt bigger than the limit by setting opening balance negative
    stmt = current_statement_factory(user=user, opening_balance=-200_000)
    # No lines required; closing == opening for this test

    stmt.refresh_from_db()
    assert stmt.status == StatementStatus.CURRENT
    assert stmt.closing_balance == -200_000

    assert limit.available_limit == 0


# ---------- grace_days property ----------

def test_grace_days_override(user, active_credit_limit_factory):
    limit = active_credit_limit_factory(user=user, grace_days=7)  # factory should map to grace_period_days
    assert limit.grace_days == 7


def test_grace_days_default_follows_settings(monkeypatch, user, active_credit_limit_factory):
    # Patch the imported constant inside 'credit.utils.constants'
    monkeypatch.setattr(
        'credit.models.credit_limit.STATEMENT_GRACE_DAYS', 15, raising=False
        )
    limit = active_credit_limit_factory(user=user, grace_days=None)
    assert limit.grace_days == 15


# ---------- Activation / Deactivation semantics ----------

def test_activate_keeps_only_one_active(user, active_credit_limit_factory):
    first = active_credit_limit_factory(user=user, is_active=True, approved_limit=1_000_000)
    second = active_credit_limit_factory(user=user, is_active=False, approved_limit=2_000_000)

    second.activate()

    first.refresh_from_db()
    second.refresh_from_db()

    assert second.is_active is True
    assert first.is_active is False
    assert CreditLimit.objects.filter(user=user, is_active=True).count() == 1


def test_deactivate_user_active_limits_bulk(user, active_credit_limit_factory):
    a = active_credit_limit_factory(user=user, is_active=True)
    b = active_credit_limit_factory(user=user, is_active=False)
    changed = CreditLimit.deactivate_user_active_limits(user)
    assert changed in (0, 1)  # only 'a' could be active
    a.refresh_from_db()
    assert a.is_active is False
    assert CreditLimit.objects.filter(user=user, is_active=True).count() == 0


# ---------- DB constraints & reference_code generation ----------

def test_db_unique_constraint_allows_only_one_active_per_user(user, active_credit_limit_factory):
    # Create the first active limit
    active_credit_limit_factory(user=user, is_active=True)

    # Attempt to create another active for the same user must fail at DB level
    with pytest.raises(IntegrityError):
        CreditLimit.objects.create(
            user=user,
            approved_limit=123_456,
            is_active=True,
            expiry_date=timezone.localdate() + timezone.timedelta(days=10),
        )
    # Do not query further within this test to avoid broken transaction issues.


def test_reference_code_is_generated(user, active_credit_limit_factory):
    limit = active_credit_limit_factory(user=user, is_active=False)  # avoid unique-active constraint interplay
    assert limit.reference_code
    assert CreditLimit.objects.exclude(reference_code=None).count() == 1


def test_reference_code_retries_on_collision(monkeypatch, user):
    # Pre-create an object with a known reference_code
    existing = CreditLimit.objects.create(
        user=user,
        approved_limit=111,
        is_active=False,
        expiry_date=timezone.localdate() + timezone.timedelta(days=1),
        reference_code="CR-DUP",
    )
    assert existing.reference_code == "CR-DUP"

    # Force generator to return a duplicate first, then a unique value
    from credit.models import credit_limit as cl_mod

    calls = {"n": 0}

    def fake_gen(prefix="CR"):
        calls["n"] += 1
        return "CR-DUP" if calls["n"] == 1 else "CR-UNIQ"

    monkeypatch.setattr(cl_mod, "generate_reference_code", fake_gen)

    obj = CreditLimit(
        user=user,
        approved_limit=222,
        is_active=False,
        expiry_date=timezone.localdate() + timezone.timedelta(days=2),
    )
    obj.save()  # should retry and succeed with "CR-UNIQ"

    assert obj.reference_code == "CR-UNIQ"


# ---------- __str__ ----------

def test_str_contains_user_and_formatted_amount(user, active_credit_limit_factory):
    limit = active_credit_limit_factory(user=user, approved_limit=1_234_567, is_active=False)
    s = str(limit)
    # Expect a human-readable string with thousands-separators and currency
    assert user.username in s or str(user.id) in s
    assert "1,234,567" in s
    assert "ریال" in s
