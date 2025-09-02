# credit/tests/unit/models/test_statement.py

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from persiantools.jdatetime import JalaliDate

from credit.models.statement import Statement
from credit.utils.choices import StatementStatus, StatementLineType
from credit.utils.constants import (
    MINIMUM_PAYMENT_PERCENTAGE,
    MINIMUM_PAYMENT_THRESHOLD,
    STATEMENT_PENALTY_RATE,
    STATEMENT_MAX_PENALTY_RATE,
    MONTHLY_INTEREST_RATE,
)

pytestmark = pytest.mark.django_db


# ---------- Helpers ----------

def _shift_month(year: int, month: int, delta: int):
    """
    Shift a Jalali (year, month) by delta months (delta can be negative).
    Returns a normalized (year, month) pair in [1..12].
    """
    total = (year * 12 + (month - 1)) + delta
    ny = total // 12
    nm = (total % 12) + 1
    return ny, nm


# ---------- Core mechanics: balances ----------

def test_update_balances_calculates_totals_and_closing(user):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT, opening_balance=10_000
    )
    # debit: 30_000 | credit: 12_000
    stmt.add_line(StatementLineType.PURCHASE, 20_000)
    stmt.add_line(StatementLineType.PURCHASE, 10_000)
    stmt.add_line(StatementLineType.PAYMENT, 12_000)
    stmt.refresh_from_db()

    assert stmt.total_debit == 30_000
    assert stmt.total_credit == 12_000
    # closing = opening + credit - debit
    assert stmt.closing_balance == 10_000 + 12_000 - 30_000  # => -8_000


def test_update_balances_no_lines_keeps_opening_as_closing(user):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT, opening_balance=123_456
    )
    # No lines -> closing should remain equal to opening
    stmt.update_balances()
    stmt.refresh_from_db()
    assert stmt.total_debit == 0
    assert stmt.total_credit == 0
    assert stmt.closing_balance == 123_456


# ---------- Manager: get_or_create_current_statement ----------

def test_manager_get_or_create_current_creates_and_reuses(user):
    stmt1, created1 = Statement.objects.get_or_create_current_statement(user)
    stmt2, created2 = Statement.objects.get_or_create_current_statement(user)

    assert created1 is True
    assert created2 is False
    assert stmt1.id == stmt2.id
    today = JalaliDate.today()
    assert stmt1.year == today.year and stmt1.month == today.month
    assert stmt1.status == StatementStatus.CURRENT


# ---------- Closing a statement ----------

def test_close_statement_sets_pending_and_due_date(
        user, active_credit_limit_factory
):
    # Arrange: active credit-limit with 10 days grace
    active_credit_limit_factory(user=user, grace_days=10)
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT
    )

    # Act
    before = timezone.now()
    stmt.close_statement()
    after = timezone.now()

    # Assert
    stmt.refresh_from_db()
    assert stmt.status == StatementStatus.PENDING_PAYMENT
    assert stmt.closed_at is not None and before <= stmt.closed_at <= after
    assert stmt.due_date is not None
    assert (stmt.due_date - stmt.closed_at).days == 10


def test_close_statement_is_noop_when_not_current(user):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.PENDING_PAYMENT
    )
    # Calling close_statement on non-CURRENT should not change status
    stmt.close_statement()
    stmt.refresh_from_db()
    assert stmt.status == StatementStatus.PENDING_PAYMENT


def test_close_statement_recomputes_balances_before_closing(
        user, active_credit_limit_factory
):
    """close_statement must recompute balances so closing reflects lines."""
    active_credit_limit_factory(user=user, grace_days=1)
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT, opening_balance=0
    )
    stmt.add_line(
        StatementLineType.PURCHASE, 50_000
    )  # -> closing should be -50_000
    stmt.add_line(
        StatementLineType.PAYMENT, 10_000
    )  # -> closing should be -40_000

    stmt.close_statement()
    stmt.refresh_from_db()
    assert stmt.status == StatementStatus.PENDING_PAYMENT
    assert stmt.closing_balance == -40_000


def test_close_statement_without_credit_limit_sets_due_now(user):
    """
    If there is no active CreditLimit, grace_days resolves to 0 and due_date == closed_at.
    """
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT
    )
    stmt.close_statement()
    stmt.refresh_from_db()
    assert stmt.status == StatementStatus.PENDING_PAYMENT
    assert stmt.due_date is not None and stmt.closed_at is not None
    assert (stmt.due_date - stmt.closed_at).days == 0


# ---------- is_within_due ----------

def test_is_within_due_true_and_false_and_none(user):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.PENDING_PAYMENT
    )
    now = timezone.now()

    # due in future -> True
    stmt.due_date = now + timedelta(days=2)
    assert stmt.is_within_due(now=now) is True

    # due in past -> False
    stmt.due_date = now - timedelta(days=1)
    assert stmt.is_within_due(now=now) is False

    # due_date None -> False
    stmt.due_date = None
    assert stmt.is_within_due(now=now) is False


def test_is_within_due_uses_default_now(user):
    """When 'now' is not provided, method should rely on timezone.now()."""
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.PENDING_PAYMENT,
        due_date=timezone.now() + timedelta(seconds=1),
    )
    assert stmt.is_within_due() is True


# ---------- Minimum payment ----------

def test_calculate_minimum_payment_amount_threshold_and_percentage(user):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.PENDING_PAYMENT
    )

    # Debt below threshold -> zero
    stmt.closing_balance = -(MINIMUM_PAYMENT_THRESHOLD - 1)
    assert stmt.calculate_minimum_payment_amount() == 0

    # Debt equals threshold -> percentage
    stmt.closing_balance = -MINIMUM_PAYMENT_THRESHOLD
    assert stmt.calculate_minimum_payment_amount() == int(
        MINIMUM_PAYMENT_THRESHOLD * MINIMUM_PAYMENT_PERCENTAGE
    )

    # Debt above threshold -> percentage
    stmt.closing_balance = -1_000_000
    assert stmt.calculate_minimum_payment_amount() == int(
        1_000_000 * MINIMUM_PAYMENT_PERCENTAGE
    )


# ---------- Due window outcome ----------

def test_determine_due_outcome_no_penalty_when_enough_payment(user):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.PENDING_PAYMENT
    )
    stmt.closing_balance = -1_000_000
    min_required = stmt.calculate_minimum_payment_amount()

    outcome = stmt.determine_due_outcome(
        total_payments_during_due=min_required
    )
    assert outcome == StatementStatus.CLOSED_NO_PENALTY
    assert stmt.closed_at is not None


def test_determine_due_outcome_with_penalty_when_insufficient_payment(user):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.PENDING_PAYMENT
    )
    stmt.closing_balance = -1_000_000
    min_required = stmt.calculate_minimum_payment_amount()

    outcome = stmt.determine_due_outcome(
        total_payments_during_due=min_required - 1
    )
    assert outcome == StatementStatus.CLOSED_WITH_PENALTY
    assert stmt.closed_at is not None


def test_determine_due_outcome_below_threshold_closes_without_penalty(user):
    """When debt is below minimum threshold, it should close without penalty regardless of payments."""
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.PENDING_PAYMENT,
        closing_balance=-(MINIMUM_PAYMENT_THRESHOLD - 1),
    )
    outcome = stmt.determine_due_outcome(total_payments_during_due=0)
    assert outcome == StatementStatus.CLOSED_NO_PENALTY


def test_determine_due_outcome_raises_on_non_pending(user):
    """Calling determine_due_outcome on non-PENDING statements must raise."""
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT,
    )
    with pytest.raises(ValueError):
        stmt.determine_due_outcome(total_payments_during_due=0)


# ---------- Penalty computation ----------

def test_compute_penalty_amount_respects_rate_and_cap(user):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.PENDING_PAYMENT
    )
    # Base debt 2,000,000; due date 5 days ago
    stmt.closing_balance = -2_000_000
    stmt.due_date = timezone.now() - timedelta(days=5)

    expected = int(2_000_000 * STATEMENT_PENALTY_RATE * 5)
    cap = int(2_000_000 * STATEMENT_MAX_PENALTY_RATE)

    computed = stmt.compute_penalty_amount()
    assert computed == min(expected, cap)


def test_compute_penalty_amount_zero_when_not_pending_or_not_past_due_or_non_negative(
        user
):
    """
    Build four statements on distinct months to avoid the (user, year, month) unique constraint:
      - s1: status != PENDING -> 0
      - s2: PENDING but no due_date -> 0
      - s3: PENDING but non-negative balance -> 0
      - s4: PENDING and negative balance but not past due -> 0
    """
    today = JalaliDate.today()
    y0, m0 = today.year, today.month
    y1, m1 = _shift_month(y0, m0, -1)
    y2, m2 = _shift_month(y0, m0, -2)
    y3, m3 = _shift_month(y0, m0, -3)

    s1 = Statement.objects.create(
        user=user, year=y0, month=m0,
        status=StatementStatus.CURRENT, closing_balance=-1,
        due_date=timezone.now() - timedelta(days=1)
    )
    assert s1.compute_penalty_amount() == 0

    s2 = Statement.objects.create(
        user=user, year=y1, month=m1,
        status=StatementStatus.PENDING_PAYMENT, closing_balance=-1,
        due_date=None
    )
    assert s2.compute_penalty_amount() == 0

    s3 = Statement.objects.create(
        user=user, year=y2, month=m2,
        status=StatementStatus.PENDING_PAYMENT, closing_balance=0,
        due_date=timezone.now() - timedelta(days=1)
    )
    assert s3.compute_penalty_amount() == 0

    s4 = Statement.objects.create(
        user=user, year=y3, month=m3,
        status=StatementStatus.PENDING_PAYMENT, closing_balance=-1000,
        due_date=timezone.now() + timedelta(days=1)
    )
    assert s4.compute_penalty_amount() == 0


# ---------- Interest carry-over helper (instance-level) ----------

def test_add_monthly_interest_on_carryover_adds_line_only_on_negative_and_current(
        user
):
    """
    add_monthly_interest_on_carryover:
      - must be called on CURRENT statements
      - adds an INTEREST line iff previous_stmt.closing_balance < 0
      - calling it on NON-CURRENT should raise
    """
    today = JalaliDate.today()
    cy, cm = today.year, today.month

    # CURRENT for (cy, cm)
    current_stmt = Statement.objects.create(
        user=user, year=cy, month=cm, status=StatementStatus.CURRENT
    )

    # previous (negative closing) -> expect an INTEREST line on current
    py1, pm1 = _shift_month(cy, cm, -1)
    prev_neg = Statement.objects.create(
        user=user, year=py1, month=pm1,
        status=StatementStatus.PENDING_PAYMENT, closing_balance=-200_000
    )
    current_stmt.add_monthly_interest_on_carryover(prev_neg)
    expected = int(abs(prev_neg.closing_balance) * MONTHLY_INTEREST_RATE)
    assert current_stmt.lines.filter(
        type=StatementLineType.INTEREST, amount=-expected
    ).count() == 1

    # previous (non-negative closing) -> no extra interest lines
    py2, pm2 = _shift_month(cy, cm, -2)
    prev_nonneg = Statement.objects.create(
        user=user, year=py2, month=pm2,
        status=StatementStatus.PENDING_PAYMENT, closing_balance=0
    )
    current_stmt.add_monthly_interest_on_carryover(prev_nonneg)
    assert current_stmt.lines.filter(
        type=StatementLineType.INTEREST
    ).count() == 1  # unchanged

    # NON-CURRENT target should raise -> place it on a distinct month to avoid (user, year, month) uniqueness
    ny, nm = _shift_month(cy, cm, +1)
    non_current = Statement.objects.create(
        user=user, year=ny, month=nm, status=StatementStatus.PENDING_PAYMENT
    )
    with pytest.raises(ValueError):
        non_current.add_monthly_interest_on_carryover(prev_neg)


def test_add_monthly_interest_on_carryover_duplicate_interest_raises(user):
    """A second INTEREST line on the same CURRENT statement should violate the unique constraint."""
    today = JalaliDate.today()
    cy, cm = today.year, today.month
    current_stmt = Statement.objects.create(
        user=user, year=cy, month=cm, status=StatementStatus.CURRENT
    )
    py1, pm1 = _shift_month(cy, cm, -1)
    prev_neg_1 = Statement.objects.create(
        user=user, year=py1, month=pm1,
        status=StatementStatus.PENDING_PAYMENT, closing_balance=-100_000
    )
    # First add => ok
    current_stmt.add_monthly_interest_on_carryover(prev_neg_1)

    # Second add with another negative previous => should fail due to unique (statement, type=INTEREST)
    py2, pm2 = _shift_month(cy, cm, -2)
    prev_neg_2 = Statement.objects.create(
        user=user, year=py2, month=pm2,
        status=StatementStatus.PENDING_PAYMENT, closing_balance=-50_000
    )

    # Django validates the DB UniqueConstraint during full_clean(), so we expect ValidationError here.
    with pytest.raises((ValidationError, IntegrityError)) as exc:
        current_stmt.add_monthly_interest_on_carryover(prev_neg_2)

    # Make sure the error is indeed about our constraint.
    assert "uniq_interest_per_statement" in str(exc.value)


# ---------- Reference code generation ----------

def test_statement_reference_code_is_generated(user):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT
    )
    assert stmt.reference_code is not None


def test_statement_reference_code_retries_on_collision(monkeypatch, user):
    # Pre-create with a known code (on a different month to avoid (user, year, month) conflict)
    today = JalaliDate.today()
    py, pm = _shift_month(today.year, today.month, -1)
    existing = Statement.objects.create(
        user=user, year=py, month=pm,
        status=StatementStatus.CURRENT,
        reference_code="ST-DUP",
    )
    assert existing.reference_code == "ST-DUP"

    from credit.models import statement as st_mod
    calls = {"n": 0}

    def fake_gen(prefix="ST"):
        calls["n"] += 1
        return "ST-DUP" if calls["n"] == 1 else "ST-UNIQ"

    monkeypatch.setattr(st_mod, "generate_reference_code", fake_gen)

    obj = Statement(
        user=user,
        year=today.year,
        month=today.month,
        status=StatementStatus.CURRENT,
    )
    obj.save()
    assert obj.reference_code == "ST-UNIQ"


# --- add_payment: success and guards ---

def test_add_payment_success_creates_positive_payment_line(user):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT, opening_balance=0
    )
    stmt.add_payment(5_000, description="Pay")
    stmt.refresh_from_db()
    # payment stored positive
    assert stmt.lines.filter(
        type=StatementLineType.PAYMENT, amount=5_000
    ).count() == 1
    # closing = 0 + 5_000 - 0
    assert stmt.closing_balance == 5_000


def test_add_payment_raises_on_zero_amount(user):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT
    )
    with pytest.raises(ValueError):
        stmt.add_payment(0)

def test_add_payment_raises_on_non_current(user):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.PENDING_PAYMENT
    )
    with pytest.raises(ValueError):
        stmt.add_payment(1000)


# --- add_purchase: validations and happy-path ---

def _make_dummy_tx(user_id, amount, status_ok=True, belong="from"):
    # Minimal stub for transaction object (no DB row needed)
    class _W:
        def __init__(self, uid): self.user_id = uid

    class _T:
        pass

    from wallets.utils.choices import TransactionStatus
    t = _T()
    t.amount = amount
    t.status = TransactionStatus.SUCCESS if status_ok else "NOT_SUCCESS"
    t.from_wallet = _W(user_id if belong in ("from", "both") else 999_001)
    t.to_wallet = _W(user_id if belong in ("to", "both") else 999_002)
    return t


def _stub_credit_limit(is_active=True, days_ahead=10, available=1_000_000):
    class _CL:
        def __init__(self):
            from django.utils import timezone
            self.is_active = is_active
            self.expiry_date = timezone.localdate() + timezone.timedelta(
                days=days_ahead
            )
            self.available_limit = available

    return _CL()


def test_add_purchase_raises_on_non_current(user, monkeypatch):
    # PENDING -> not allowed
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.PENDING_PAYMENT
    )
    # stub credit limit to avoid unrelated errors
    from credit.models.credit_limit import CreditLimit
    monkeypatch.setattr(
        CreditLimit.objects, "get_user_credit_limit",
        lambda u: _stub_credit_limit()
    )
    with pytest.raises(ValueError):
        stmt.add_purchase(
            _make_dummy_tx(user.id, 10_000, status_ok=True, belong="both")
        )


def test_add_purchase_raises_on_non_success_tx(user, monkeypatch):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT
    )
    from credit.models.credit_limit import CreditLimit
    monkeypatch.setattr(
        CreditLimit.objects, "get_user_credit_limit",
        lambda u: _stub_credit_limit()
    )
    with pytest.raises(ValueError):
        stmt.add_purchase(
            _make_dummy_tx(user.id, 10_000, status_ok=False, belong="both")
        )


def test_add_purchase_raises_when_tx_not_belongs_to_user(user, monkeypatch):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT
    )
    from credit.models.credit_limit import CreditLimit
    monkeypatch.setattr(
        CreditLimit.objects, "get_user_credit_limit",
        lambda u: _stub_credit_limit()
    )
    with pytest.raises(ValueError):
        stmt.add_purchase(
            _make_dummy_tx(user.id, 10_000, status_ok=True, belong="none")
        )


def test_add_purchase_raises_without_active_credit_limit(user, monkeypatch):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT
    )
    from credit.models.credit_limit import CreditLimit
    monkeypatch.setattr(
        CreditLimit.objects, "get_user_credit_limit", lambda u: None
    )
    with pytest.raises(ValueError):
        stmt.add_purchase(
            _make_dummy_tx(user.id, 10_000, status_ok=True, belong="both")
        )


@pytest.mark.parametrize("is_active,days_ahead", [(False, 10), (True, 0)])
def test_add_purchase_raises_on_inactive_or_expired_limit(
        user, monkeypatch, is_active, days_ahead
):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT
    )
    from credit.models.credit_limit import CreditLimit
    monkeypatch.setattr(
        CreditLimit.objects, "get_user_credit_limit",
        lambda u: _stub_credit_limit(
            is_active=is_active, days_ahead=days_ahead
        )
    )
    with pytest.raises(ValueError):
        stmt.add_purchase(
            _make_dummy_tx(user.id, 10_000, status_ok=True, belong="both")
        )


def test_add_purchase_raises_on_insufficient_available_limit(
        user, monkeypatch
):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT
    )
    from credit.models.credit_limit import CreditLimit
    monkeypatch.setattr(
        CreditLimit.objects, "get_user_credit_limit",
        lambda u: _stub_credit_limit(available=5_000)
    )
    with pytest.raises(ValueError):
        stmt.add_purchase(
            _make_dummy_tx(user.id, 10_001, status_ok=True, belong="both")
        )


def test_add_purchase_success_calls_add_line_with_abs_amount(
        user, monkeypatch
):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT
    )
    # credit limit ok
    from credit.models.credit_limit import CreditLimit
    monkeypatch.setattr(
        CreditLimit.objects, "get_user_credit_limit",
        lambda u: _stub_credit_limit(available=999_999)
    )

    called = {}

    def fake_add_line(self, type_, amount, transaction=None, description=""):
        called["type"] = type_
        called["amount"] = amount
        called["transaction"] = transaction
        called["description"] = description

    monkeypatch.setattr(Statement, "add_line", fake_add_line, raising=False)

    trx = _make_dummy_tx(user.id, amount=12_345, status_ok=True, belong="both")
    stmt.add_purchase(trx, description="Shop A")

    # add_purchase should pass abs(amount) into add_line (sign normalization is tested elsewhere)
    assert called["type"] == StatementLineType.PURCHASE
    assert called["amount"] == 12_345
    assert called["transaction"] == trx
    assert called["description"] == "Shop A"


# --- manager: nothing to close when no CURRENT exists ---

def test_close_monthly_statements_no_currents_returns_zero():
    result = Statement.objects.close_monthly_statements()
    assert result == {
        "statements_closed": 0,
        "statements_created": 0,
        "interest_lines_added": 0,
    }


# --- minimum payment: non-pending or non-negative must be zero ---

@pytest.mark.parametrize(
    "status,closing,expected", [
        (StatementStatus.CURRENT, -100_000, 0),
        (StatementStatus.PENDING_PAYMENT, 100_000, 0),
    ]
)
def test_minimum_payment_zero_when_not_pending_or_non_negative(
        user, status, closing, expected
):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month, status=status,
        closing_balance=closing
    )
    assert stmt.calculate_minimum_payment_amount() == expected


# --- Statement reference_code: 5 collisions -> NULL fallback ---

def test_statement_reference_code_five_collisions_then_null(monkeypatch, user):
    from credit.models import statement as st_mod

    def dup_gen(prefix="ST"): return "ST-DUP"

    monkeypatch.setattr(st_mod, "generate_reference_code", dup_gen)
    # pre-create with the dup code to ensure collisions
    today = JalaliDate.today()
    # use previous month to avoid (user,year,month) uniqueness
    py, pm = (today.year - (1 if today.month == 1 else 0),
              12 if today.month == 1 else today.month - 1)
    Statement.objects.create(
        user=user, year=py, month=pm,
        status=StatementStatus.CURRENT, reference_code="ST-DUP"
    )

    obj = Statement(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT
    )
    obj.save()
    assert obj.reference_code is None  # fell back after 5 collisions


# --- __str__ formatting ---

def test_statement_str_format(user):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT
    )
    s = str(stmt)
    assert f"{today.year}/{today.month:02d}" in s
    assert "(" in s and ")" in s

def test_add_payment_accepts_negative_and_normalizes_to_positive(user):
    today = JalaliDate.today()
    stmt = Statement.objects.create(
        user=user, year=today.year, month=today.month,
        status=StatementStatus.CURRENT, opening_balance=0
    )
    stmt.add_payment(-3_000, description="neg")
    stmt.refresh_from_db()

    # A positive PAYMENT line must be stored
    assert stmt.lines.filter(type=StatementLineType.PAYMENT, amount=3_000).count() == 1
    assert stmt.closing_balance == 3_000