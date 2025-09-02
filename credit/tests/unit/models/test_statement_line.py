# tests/unit/models/test_statement_line.py

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from persiantools.jdatetime import JalaliDate

from credit.models.statement import Statement
from credit.models.statement_line import StatementLine
from credit.utils.choices import StatementStatus, StatementLineType

pytestmark = pytest.mark.django_db


# ---------- Helpers ----------

def _shift_month(year: int, month: int, delta: int):
    """
    Shift a Jalali (year, month) by delta months (delta can be negative).
    Returns a normalized (year, month) in [1..12].
    """
    total = (year * 12 + (month - 1)) + delta
    ny = total // 12
    nm = (total % 12) + 1
    return ny, nm


def _make_statement(user, status, opening=0, y=None, m=None):
    """
    Create a statement for the given user/status on a specific Jalali (year, month).
    If y/m omitted, it uses the current Jalali month.
    """
    today = JalaliDate.today()
    y = y or today.year
    m = m or today.month
    return Statement.objects.create(
        user=user, year=y, month=m, status=status, opening_balance=opening
    )


# ---------- amount validation & normalization ----------

def test_line_cannot_have_zero_amount(user):
    stmt = _make_statement(user, StatementStatus.CURRENT)
    with pytest.raises(ValidationError):
        StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PURCHASE, amount=0
        )


def test_sign_normalization_by_type(user):
    stmt = _make_statement(user, StatementStatus.CURRENT)

    # PURCHASE with positive amount -> must be stored negative
    line1 = StatementLine.objects.create(
        statement=stmt, type=StatementLineType.PURCHASE, amount=10_000
    )
    assert line1.amount == -10_000

    # PAYMENT with negative amount -> must be stored positive
    line2 = StatementLine.objects.create(
        statement=stmt, type=StatementLineType.PAYMENT, amount=-5_000
    )
    assert line2.amount == 5_000


# ---------- allowed types vs. statement status ----------

def test_type_allowed_on_status_rules(user):
    # Use distinct months to avoid (user, year, month) uniqueness conflict
    today = JalaliDate.today()
    cy, cm = today.year, today.month
    py, pm = _shift_month(cy, cm, -1)

    current_stmt = _make_statement(user, StatementStatus.CURRENT, y=cy, m=cm)
    pending_stmt = _make_statement(
        user, StatementStatus.PENDING_PAYMENT, y=py, m=pm
    )

    # PURCHASE only on CURRENT
    StatementLine.objects.create(
        statement=current_stmt, type=StatementLineType.PURCHASE, amount=10_000
    )
    with pytest.raises(ValidationError):
        StatementLine.objects.create(
            statement=pending_stmt, type=StatementLineType.PURCHASE,
            amount=10_000
        )

    # PAYMENT only on CURRENT
    StatementLine.objects.create(
        statement=current_stmt, type=StatementLineType.PAYMENT, amount=5_000
    )
    with pytest.raises(ValidationError):
        StatementLine.objects.create(
            statement=pending_stmt, type=StatementLineType.PAYMENT,
            amount=5_000
        )

    # FEE only on CURRENT
    StatementLine.objects.create(
        statement=current_stmt, type=StatementLineType.FEE, amount=7_000
    )
    with pytest.raises(ValidationError):
        StatementLine.objects.create(
            statement=pending_stmt, type=StatementLineType.FEE, amount=7_000
        )

    # INTEREST only on CURRENT
    StatementLine.objects.create(
        statement=current_stmt, type=StatementLineType.INTEREST, amount=9_000
    )
    with pytest.raises(ValidationError):
        StatementLine.objects.create(
            statement=pending_stmt, type=StatementLineType.INTEREST,
            amount=9_000
        )

    # PENALTY only on CURRENT
    StatementLine.objects.create(
        statement=current_stmt, type=StatementLineType.PENALTY, amount=11_000
    )
    with pytest.raises(ValidationError):
        StatementLine.objects.create(
            statement=pending_stmt, type=StatementLineType.PENALTY,
            amount=11_000
        )


# ---------- uniqueness: single INTEREST per statement ----------

def test_only_one_interest_line_per_statement(user):
    stmt = _make_statement(user, StatementStatus.CURRENT)
    StatementLine.objects.create(
        statement=stmt, type=StatementLineType.INTEREST, amount=10_000
    )
    # Rely on DB unique constraint to reject a second INTEREST for the same statement
    with pytest.raises(Exception):
        StatementLine.objects.create(
            statement=stmt, type=StatementLineType.INTEREST, amount=20_000
        )


# ---------- parent balance recomputation ----------

def test_parent_balances_recomputed_on_create_and_on_amount_change(user):
    stmt = _make_statement(user, StatementStatus.CURRENT, opening=0)

    # Create a purchase -> totals should reflect 10_000 debit
    line = StatementLine.objects.create(
        statement=stmt, type=StatementLineType.PURCHASE, amount=10_000
    )
    stmt.refresh_from_db()
    assert stmt.total_debit == 10_000
    assert stmt.total_credit == 0
    assert stmt.closing_balance == -10_000

    # Update amount (via update_fields) -> totals should be recomputed to 20_000 debit
    line.amount = 20_000  # will be normalized to -20_000
    line.save(update_fields=["amount"])
    stmt.refresh_from_db()
    assert stmt.total_debit == 20_000
    assert stmt.total_credit == 0
    assert stmt.closing_balance == -20_000


def test_parent_balances_recomputed_on_type_change(user):
    stmt = _make_statement(user, StatementStatus.CURRENT, opening=0)

    # Start with a PURCHASE of 10_000 (stored as -10_000)
    line = StatementLine.objects.create(
        statement=stmt, type=StatementLineType.PURCHASE, amount=10_000
    )
    stmt.refresh_from_db()
    assert stmt.total_debit == 10_000
    assert stmt.total_credit == 0
    assert stmt.closing_balance == -10_000

    # Change type to PAYMENT -> amount normalized positive; totals flip to credit
    line.type = StatementLineType.PAYMENT
    line.save(update_fields=["type"])
    stmt.refresh_from_db()
    assert stmt.total_debit == 0
    assert stmt.total_credit == 10_000
    assert stmt.closing_balance == 10_000


# ---------- DB-level guard: amount sign by type (bulk_create bypasses save()) ----------

def test_db_check_constraint_rejects_negative_payment_on_bulk_create(user):
    """
    Using bulk_create() bypasses model.save() (and its normalization),
    so the DB CheckConstraint('amount_sign_by_type') must reject invalid signs.
    """
    stmt = _make_statement(user, StatementStatus.CURRENT)
    with pytest.raises(IntegrityError):
        StatementLine.objects.bulk_create(
            [StatementLine(
                statement=stmt, type=StatementLineType.PAYMENT, amount=-1000
            )]
        )
    # Do not query further in this test to avoid broken transaction.


def test_db_check_constraint_rejects_positive_purchase_on_bulk_create(user):
    stmt = _make_statement(user, StatementStatus.CURRENT)
    with pytest.raises(IntegrityError):
        StatementLine.objects.bulk_create(
            [StatementLine(
                statement=stmt, type=StatementLineType.PURCHASE, amount=1000
            )]
        )
    # Do not query further in this test to avoid broken transaction.


# ---------- transaction ownership (clean) ----------

def test_transaction_must_belong_to_statement_user__mismatch_raises(
        user, monkeypatch
):
    """
    When a transaction is attached, it must belong to the statement's user.
    We stub:
      1) the FK field validator to skip DB existence check;
      2) the Transaction.objects used inside clean() to return a mismatching pair.
    """
    from credit.models.statement_line import StatementLine
    from credit.models import statement_line as stl_mod

    stmt = _make_statement(user, StatementStatus.CURRENT)

    # 1) Bypass FK existence check: field.validate(value, instance) -> None
    fk_field = StatementLine._meta.get_field("transaction")
    monkeypatch.setattr(
        fk_field, "validate", lambda v, inst: None, raising=False
    )

    # 2) Stub the manager used in clean(): first() -> (from_user_id, to_user_id)
    class _QS:
        def filter(self, *args, **kwargs): return self

        def values_list(self, *args, **kwargs): return self

        def first(self): return (999001, 999002)  # neither equals stmt.user_id

    monkeypatch.setattr(
        stl_mod, "Transaction", type("T", (), {"objects": _QS()})(),
        raising=False
    )

    with pytest.raises(ValidationError):
        StatementLine.objects.create(
            statement=stmt,
            type=StatementLineType.PURCHASE,
            amount=10_000,
            transaction_id=42,  # any id; existence check is bypassed
        )


def test_transaction_belongs_to_statement_user__passes(user, monkeypatch):
    """
    Ownership check should pass if statement.user_id matches either from_wallet.user_id or to_wallet.user_id.
    We avoid saving to DB to prevent FK constraint; we only run full_clean().
    """
    from credit.models.statement_line import StatementLine
    from credit.models import statement_line as stl_mod

    stmt = _make_statement(user, StatementStatus.CURRENT)

    # Bypass FK existence validation on the field
    fk_field = StatementLine._meta.get_field("transaction")
    monkeypatch.setattr(
        fk_field, "validate", lambda v, inst: None, raising=False
    )

    # Stub Transaction.objects to return (from_user_id, to_user_id)
    class _QS:
        def __init__(self, pair): self._pair = pair

        def filter(self, *args, **kwargs): return self

        def values_list(self, *args, **kwargs): return self

        def first(self): return self._pair

    ok_mgr = _QS(
        (stmt.user_id, 999_002)
    )  # one side matches the statement's user
    monkeypatch.setattr(
        stl_mod, "Transaction", type("T", (), {"objects": ok_mgr})(),
        raising=False
    )

    # Build but do not save; run full_clean() to exercise model.clean()
    line = StatementLine(
        statement=stmt,
        type=StatementLineType.PURCHASE,
        amount=-10_000,
        # correct sign for PURCHASE because we call full_clean()
        transaction_id=777,
    )
    line.full_clean()  # should NOT raise


# ---------- non-financial update should not recompute ----------

def test_updating_description_does_not_recompute_parent_balances(user):
    """
    Only amount/type changes should trigger a parent balance recompute.
    Updating a non-financial field (description) must keep balances untouched.
    """
    stmt = _make_statement(user, StatementStatus.CURRENT, opening=0)
    line = StatementLine.objects.create(
        statement=stmt, type=StatementLineType.PURCHASE, amount=10_000
    )
    stmt.refresh_from_db()
    closing_before = stmt.closing_balance
    debit_before = stmt.total_debit
    credit_before = stmt.total_credit

    # Change only description via update_fields (no recompute expected)
    line.description = "Updated"
    line.save(update_fields=["description"])

    stmt.refresh_from_db()
    assert stmt.closing_balance == closing_before
    assert stmt.total_debit == debit_before
    assert stmt.total_credit == credit_before


def test_transaction_is_optional_none_is_valid(user):
    """transaction is optional; None should pass validation."""
    stmt = _make_statement(user, StatementStatus.CURRENT)
    StatementLine.objects.create(
        statement=stmt, type=StatementLineType.PURCHASE, amount=10_000,
        transaction=None
    )


# ---------- extra: sign normalization for FEE / PENALTY / INTEREST ----------

def test_sign_normalization_for_fee_penalty_interest(user):
    stmt = _make_statement(user, StatementStatus.CURRENT)

    fee = StatementLine.objects.create(
        statement=stmt, type=StatementLineType.FEE, amount=12_345
        # positive -> stored negative
    )
    penalty = StatementLine.objects.create(
        statement=stmt, type=StatementLineType.PENALTY, amount=23_456
        # positive -> stored negative
    )
    interest = StatementLine.objects.create(
        statement=stmt, type=StatementLineType.INTEREST, amount=34_567
        # positive -> stored negative
    )

    assert fee.amount < 0
    assert penalty.amount < 0
    assert interest.amount < 0


# ---------- new policy: delete is blocked; use void() ----------

def test_delete_is_blocked_and_balances_remain_unchanged(user):
    """
    Deleting a statement line is not allowed. It must raise ValidationError and keep balances untouched.
    """
    stmt = _make_statement(user, StatementStatus.CURRENT, opening=0)
    p = StatementLine.objects.create(
        statement=stmt, type=StatementLineType.PURCHASE, amount=10_000
        # -> -10_000
    )
    c = StatementLine.objects.create(
        statement=stmt, type=StatementLineType.PAYMENT, amount=3_000
        # -> +3_000
    )
    stmt.refresh_from_db()
    assert (stmt.total_debit, stmt.total_credit, stmt.closing_balance) == (
        10_000, 3_000, -7_000)

    with pytest.raises(ValidationError):
        c.delete()

    # Balances must remain unchanged after failed delete
    stmt.refresh_from_db()
    assert (stmt.total_debit, stmt.total_credit, stmt.closing_balance) == (
        10_000, 3_000, -7_000)


def test_void_reverses_effect_and_recomputes_parent_balances(user):
    """
    void() should neutralize the effect of a line (e.g., payment),
    by creating a compensating entry and recomputing parent balances.
    """
    stmt = _make_statement(user, StatementStatus.CURRENT, opening=0)

    StatementLine.objects.create(
        statement=stmt, type=StatementLineType.PURCHASE, amount=10_000
        # -> -10_000
    )
    pay = StatementLine.objects.create(
        statement=stmt, type=StatementLineType.PAYMENT, amount=3_000
        # -> +3_000
    )
    stmt.refresh_from_db()
    assert (stmt.total_debit, stmt.total_credit, stmt.closing_balance) == (
        10_000, 3_000, -7_000)

    # Use the supported API instead of delete()
    pay.void(reason="test-void")

    # After voiding the payment, totals should reflect no payment effect
    stmt.refresh_from_db()
    assert stmt.total_debit == 10_000
    assert stmt.total_credit == 0
    assert stmt.closing_balance == -10_000


# ---------- extra: amount cannot be set to zero on update ----------

def test_updating_amount_to_zero_raises_validation_error(user):
    stmt = _make_statement(user, StatementStatus.CURRENT)
    line = StatementLine.objects.create(
        statement=stmt, type=StatementLineType.PURCHASE, amount=10_000
    )
    line.amount = 0
    with pytest.raises(ValidationError):
        line.save(update_fields=["amount"])


# ---------- extra: DB-level guard via bulk_update (bypasses save()) ----------

def test_db_check_constraint_violated_on_bulk_update_for_payment_negative(
        user
):
    stmt = _make_statement(user, StatementStatus.CURRENT)
    line = StatementLine.objects.create(
        statement=stmt, type=StatementLineType.PAYMENT, amount=1_000
        # valid (+)
    )
    # Force invalid sign at DB level (no model.save/full_clean)
    with pytest.raises(IntegrityError):
        StatementLine.objects.filter(id=line.id).update(amount=-1_000)
    # Don't query further; transaction will be broken after IntegrityError.


# ---------- extra: DB-level guard for positive INTEREST/PENALTY on bulk_create ----------

def test_db_check_constraint_rejects_positive_interest_on_bulk_create(user):
    stmt = _make_statement(user, StatementStatus.CURRENT)
    with pytest.raises(IntegrityError):
        StatementLine.objects.bulk_create(
            [
                StatementLine(
                    statement=stmt, type=StatementLineType.INTEREST,
                    amount=1_234
                )  # should be negative
            ]
        )


def test_db_check_constraint_rejects_positive_penalty_on_bulk_create(user):
    stmt = _make_statement(user, StatementStatus.CURRENT)
    with pytest.raises(IntegrityError):
        StatementLine.objects.bulk_create(
            [
                StatementLine(
                    statement=stmt, type=StatementLineType.PENALTY,
                    amount=2_345
                )  # should be negative
            ]
        )


# ---------- extra: transaction ownership passes when 'to' side matches ----------

def test_transaction_belongs_to_statement_user__passes_on_to_side(
        user, monkeypatch
):
    """
    Ownership passes if statement.user_id matches either side; here we match the 'to' wallet side.
    """
    from credit.models.statement_line import StatementLine
    from credit.models import statement_line as stl_mod

    stmt = _make_statement(user, StatementStatus.CURRENT)

    # Bypass FK existence validation on the field (we don't persist the transaction)
    fk_field = StatementLine._meta.get_field("transaction")
    monkeypatch.setattr(
        fk_field, "validate", lambda v, inst: None, raising=False
    )

    # Return (from_user_id, to_user_id) with 'to' matching statement's user
    class _QS:
        def __init__(self, pair): self._pair = pair

        def filter(self, *args, **kwargs): return self

        def values_list(self, *args, **kwargs): return self

        def first(self): return self._pair

    ok_mgr = _QS((999_001, stmt.user_id))
    monkeypatch.setattr(
        stl_mod, "Transaction", type("T", (), {"objects": ok_mgr})(),
        raising=False
    )

    line = StatementLine(
        statement=stmt,
        type=StatementLineType.PURCHASE,
        amount=-10_000,
        # correct sign for PURCHASE because we call full_clean()
        transaction_id=888,
    )
    line.full_clean()  # should NOT raise
