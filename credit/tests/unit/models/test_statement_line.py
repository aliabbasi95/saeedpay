import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from persiantools.jdatetime import JalaliDate

from credit.models.statement import Statement
from credit.models.statement_line import StatementLine
from credit.utils.choices import StatementStatus, StatementLineType

pytestmark = pytest.mark.django_db


# ───────────────────────────── Helpers ───────────────────────────── #

def _shift_month(year: int, month: int, delta: int):
    """Shift a Jalali (year, month) by delta months; return normalized (year, month)."""
    total = (year * 12 + (month - 1)) + delta
    return total // 12, (total % 12) + 1


def _make_statement(user, status, opening=0, y=None, m=None):
    """Create a statement for the given user/status on the specified Jalali (year, month)."""
    today = JalaliDate.today()
    y = y or today.year
    m = m or today.month
    return Statement.objects.create(
        user=user, year=y, month=m, status=status, opening_balance=opening
    )


# ───────────────────────────── Test Classes ───────────────────────────── #

class TestAmountValidationAndNormalization:
    def test_line_cannot_have_zero_amount(self, user):
        stmt = _make_statement(user, StatementStatus.CURRENT)
        with pytest.raises(ValidationError):
            StatementLine.objects.create(
                statement=stmt, type=StatementLineType.PURCHASE, amount=0
            )

    def test_sign_normalization_by_type(self, user):
        stmt = _make_statement(user, StatementStatus.CURRENT)
        line1 = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PURCHASE, amount=10_000
        )
        assert line1.amount == -10_000
        line2 = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PAYMENT, amount=-5_000
        )
        assert line2.amount == 5_000

    def test_amount_update_normalization_keeps_sign_rules(self, user):
        """Sign must remain normalized on updates."""
        stmt = _make_statement(user, StatementStatus.CURRENT)
        line = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PAYMENT, amount=10_000
        )
        line.amount = -12_345
        line.save(update_fields=["amount"])
        line.refresh_from_db()
        assert line.amount == 12_345  # normalized to +


class TestAllowedTypesVsStatus:
    def test_rules(self, user):
        today = JalaliDate.today()
        cy, cm = today.year, today.month
        py, pm = _shift_month(cy, cm, -1)
        current_stmt = _make_statement(
            user, StatementStatus.CURRENT, y=cy, m=cm
        )
        pending_stmt = _make_statement(
            user, StatementStatus.PENDING_PAYMENT, y=py, m=pm
        )

        # PURCHASE
        StatementLine.objects.create(
            statement=current_stmt, type=StatementLineType.PURCHASE,
            amount=10_000
        )
        with pytest.raises(ValidationError):
            StatementLine.objects.create(
                statement=pending_stmt, type=StatementLineType.PURCHASE,
                amount=10_000
            )

        # PAYMENT
        StatementLine.objects.create(
            statement=current_stmt, type=StatementLineType.PAYMENT,
            amount=5_000
        )
        with pytest.raises(ValidationError):
            StatementLine.objects.create(
                statement=pending_stmt, type=StatementLineType.PAYMENT,
                amount=5_000
            )

        # FEE
        StatementLine.objects.create(
            statement=current_stmt, type=StatementLineType.FEE, amount=7_000
        )
        with pytest.raises(ValidationError):
            StatementLine.objects.create(
                statement=pending_stmt, type=StatementLineType.FEE,
                amount=7_000
            )

        # INTEREST
        StatementLine.objects.create(
            statement=current_stmt, type=StatementLineType.INTEREST,
            amount=9_000
        )
        with pytest.raises(ValidationError):
            StatementLine.objects.create(
                statement=pending_stmt, type=StatementLineType.INTEREST,
                amount=9_000
            )

        # PENALTY
        StatementLine.objects.create(
            statement=current_stmt, type=StatementLineType.PENALTY,
            amount=11_000
        )
        with pytest.raises(ValidationError):
            StatementLine.objects.create(
                statement=pending_stmt, type=StatementLineType.PENALTY,
                amount=11_000
            )


class TestUniqueness:
    def test_only_one_interest_line_per_statement(self, user):
        stmt = _make_statement(user, StatementStatus.CURRENT)
        StatementLine.objects.create(
            statement=stmt, type=StatementLineType.INTEREST, amount=10_000
        )
        with pytest.raises((ValidationError, IntegrityError)):
            StatementLine.objects.create(
                statement=stmt, type=StatementLineType.INTEREST, amount=20_000
            )


class TestParentBalanceRecompute:
    def test_on_create_and_on_amount_change(self, user):
        stmt = _make_statement(user, StatementStatus.CURRENT, opening=0)
        line = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PURCHASE, amount=10_000
        )
        stmt.refresh_from_db()
        assert (stmt.total_debit, stmt.total_credit, stmt.closing_balance) == (
            10_000, 0, -10_000)

        line.amount = 20_000  # normalized to -20_000
        line.save(update_fields=["amount"])
        stmt.refresh_from_db()
        assert (stmt.total_debit, stmt.total_credit, stmt.closing_balance) == (
            20_000, 0, -20_000)

    def test_on_type_change_purchase_to_payment(self, user):
        stmt = _make_statement(user, StatementStatus.CURRENT, opening=0)
        line = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PURCHASE, amount=10_000
        )
        stmt.refresh_from_db()
        assert (stmt.total_debit, stmt.total_credit, stmt.closing_balance) == (
            10_000, 0, -10_000)

        line.type = StatementLineType.PAYMENT
        line.save(update_fields=["type"])
        stmt.refresh_from_db()
        assert (stmt.total_debit, stmt.total_credit, stmt.closing_balance) == (
            0, 10_000, 10_000)

    def test_on_type_change_payment_to_purchase(self, user):
        stmt = _make_statement(user, StatementStatus.CURRENT, opening=0)
        line = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PAYMENT, amount=10_000
        )
        stmt.refresh_from_db()
        assert (stmt.total_debit, stmt.total_credit, stmt.closing_balance) == (
            0, 10_000, 10_000)

        line.type = StatementLineType.PURCHASE
        line.save(update_fields=["type"])
        stmt.refresh_from_db()
        assert (stmt.total_debit, stmt.total_credit, stmt.closing_balance) == (
            10_000, 0, -10_000)


class TestDBCheckConstraintsBulkPaths:
    """DB-level guards for sign by type on bulk paths (save() bypass)."""

    def test_rejects_negative_payment_on_bulk_create(self, user):
        stmt = _make_statement(user, StatementStatus.CURRENT)
        with pytest.raises(IntegrityError):
            StatementLine.objects.bulk_create(
                [StatementLine(
                    statement=stmt, type=StatementLineType.PAYMENT,
                    amount=-1000
                )]
            )

    def test_rejects_positive_purchase_on_bulk_create(self, user):
        stmt = _make_statement(user, StatementStatus.CURRENT)
        with pytest.raises(IntegrityError):
            StatementLine.objects.bulk_create(
                [StatementLine(
                    statement=stmt, type=StatementLineType.PURCHASE,
                    amount=1000
                )]
            )

    def test_rejects_positive_interest_on_bulk_create(self, user):
        stmt = _make_statement(user, StatementStatus.CURRENT)
        with pytest.raises(IntegrityError):
            StatementLine.objects.bulk_create(
                [StatementLine(
                    statement=stmt, type=StatementLineType.INTEREST,
                    amount=1_234
                )]
            )

    def test_rejects_positive_penalty_on_bulk_create(self, user):
        stmt = _make_statement(user, StatementStatus.CURRENT)
        with pytest.raises(IntegrityError):
            StatementLine.objects.bulk_create(
                [StatementLine(
                    statement=stmt, type=StatementLineType.PENALTY,
                    amount=2_345
                )]
            )

    def test_rejects_positive_fee_on_bulk_create(self, user):
        stmt = _make_statement(user, StatementStatus.CURRENT)
        with pytest.raises(IntegrityError):
            StatementLine.objects.bulk_create(
                [StatementLine(
                    statement=stmt, type=StatementLineType.FEE, amount=999
                )]
            )

    def test_violated_on_bulk_update_for_payment_negative(self, user):
        stmt = _make_statement(user, StatementStatus.CURRENT)
        line = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PAYMENT, amount=1_000
        )
        with pytest.raises(IntegrityError):
            StatementLine.objects.filter(id=line.id).update(amount=-1_000)

    def test_violated_on_bulk_update_for_purchase_positive(self, user):
        stmt = _make_statement(user, StatementStatus.CURRENT)
        line = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PURCHASE, amount=1_000
        )
        with pytest.raises(IntegrityError):
            StatementLine.objects.filter(id=line.id).update(amount=+1_000)


class TestTransactionOwnershipClean:
    def test_mismatch_raises(self, user, monkeypatch):
        """Transaction must belong to the statement's user."""
        from credit.models.statement_line import StatementLine as SL
        from credit.models import statement_line as stl_mod
        stmt = _make_statement(user, StatementStatus.CURRENT)
        fk_field = SL._meta.get_field("transaction")
        monkeypatch.setattr(
            fk_field, "validate", lambda v, inst: None, raising=False
        )

        class _QS:
            def filter(self, *args, **kwargs): return self

            def values_list(self, *args, **kwargs): return self

            def first(self): return (999001, 999002)

        monkeypatch.setattr(
            stl_mod, "Transaction", type("T", (), {"objects": _QS()})(),
            raising=False
        )
        with pytest.raises(ValidationError):
            StatementLine.objects.create(
                statement=stmt, type=StatementLineType.PURCHASE, amount=10_000,
                transaction_id=42
            )

    def test_passes_on_from_side(self, user, monkeypatch):
        from credit.models.statement_line import StatementLine as SL
        from credit.models import statement_line as stl_mod
        stmt = _make_statement(user, StatementStatus.CURRENT)
        fk_field = SL._meta.get_field("transaction")
        monkeypatch.setattr(
            fk_field, "validate", lambda v, inst: None, raising=False
        )

        class _QS:
            def __init__(self, pair): self._pair = pair

            def filter(self, *args, **kwargs): return self

            def values_list(self, *args, **kwargs): return self

            def first(self): return self._pair

        ok_mgr = _QS((stmt.user_id, 999_002))
        monkeypatch.setattr(
            stl_mod, "Transaction", type("T", (), {"objects": ok_mgr})(),
            raising=False
        )

        line = StatementLine(
            statement=stmt, type=StatementLineType.PURCHASE, amount=-10_000,
            transaction_id=777
        )
        line.full_clean()  # no raise

    def test_passes_on_to_side(self, user, monkeypatch):
        from credit.models.statement_line import StatementLine as SL
        from credit.models import statement_line as stl_mod
        stmt = _make_statement(user, StatementStatus.CURRENT)
        fk_field = SL._meta.get_field("transaction")
        monkeypatch.setattr(
            fk_field, "validate", lambda v, inst: None, raising=False
        )

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
            statement=stmt, type=StatementLineType.PURCHASE, amount=-10_000,
            transaction_id=888
        )
        line.full_clean()  # no raise


class TestNonFinancialUpdateDoesNotRecompute:
    def test_description_update_keeps_parent_balances(self, user):
        stmt = _make_statement(user, StatementStatus.CURRENT, opening=0)
        line = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PURCHASE, amount=10_000
        )
        stmt.refresh_from_db()
        closing_before, debit_before, credit_before = stmt.closing_balance, stmt.total_debit, stmt.total_credit

        line.description = "Updated"
        line.save(update_fields=["description"])
        stmt.refresh_from_db()
        assert (stmt.closing_balance, stmt.total_debit, stmt.total_credit) == (
            closing_before, debit_before, credit_before)


class TestOptionalTransactionField:
    def test_transaction_is_optional_none_is_valid(self, user):
        stmt = _make_statement(user, StatementStatus.CURRENT)
        StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PURCHASE, amount=10_000,
            transaction=None
        )


class TestFeePenaltyInterestSignNormalization:
    def test_all_are_stored_negative(self, user):
        stmt = _make_statement(user, StatementStatus.CURRENT)
        fee = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.FEE, amount=12_345
        )
        penalty = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PENALTY, amount=23_456
        )
        interest = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.INTEREST, amount=34_567
        )
        assert fee.amount < 0 and penalty.amount < 0 and interest.amount < 0


class TestDeletePolicyAndVoid:
    def test_delete_is_blocked_and_balances_remain_unchanged(self, user):
        """Deleting a line must raise and keep balances unchanged."""
        stmt = _make_statement(user, StatementStatus.CURRENT, opening=0)
        StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PURCHASE, amount=10_000
        )
        pay = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PAYMENT, amount=3_000
        )
        stmt.refresh_from_db()
        assert (stmt.total_debit, stmt.total_credit, stmt.closing_balance) == (
            10_000, 3_000, -7_000)
        with pytest.raises(ValidationError):
            pay.delete()
        stmt.refresh_from_db()
        assert (stmt.total_debit, stmt.total_credit, stmt.closing_balance) == (
            10_000, 3_000, -7_000)

    def test_void_payment_and_purchase(self, user):
        """void() should soft-deactivate and recompute parent balances."""
        stmt = _make_statement(user, StatementStatus.CURRENT, opening=0)
        p = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PURCHASE, amount=10_000
        )
        pay = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PAYMENT, amount=3_000
        )
        stmt.refresh_from_db()
        assert (stmt.total_debit, stmt.total_credit, stmt.closing_balance) == (
            10_000, 3_000, -7_000)

        before_count = stmt.lines.count()
        pay_id, p_id = pay.id, p.id

        pay.void(reason="test-void")
        stmt.refresh_from_db()
        assert stmt.lines.count() == before_count - 1
        assert not stmt.lines.filter(id=pay_id).exists()
        assert (stmt.total_debit, stmt.total_credit, stmt.closing_balance) == (
            10_000, 0, -10_000)

        # Now void the purchase
        before_count2 = stmt.lines.count()
        p.void(reason="test-void")
        stmt.refresh_from_db()
        assert stmt.lines.count() == before_count2 - 1
        assert not stmt.lines.filter(id=p_id).exists()
        assert (stmt.total_debit, stmt.total_credit, stmt.closing_balance) == (
            0, 0, 0)


class TestAmountCannotBecomeZeroOnUpdate:
    def test_amount_to_zero_raises(self, user):
        stmt = _make_statement(user, StatementStatus.CURRENT)
        line = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PURCHASE, amount=10_000
        )
        line.amount = 0
        with pytest.raises(ValidationError):
            line.save(update_fields=["amount"])
