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


# ───────────────────────────── Helpers ───────────────────────────── #

def _shift_month(year: int, month: int, delta: int):
    """Shift a Jalali (year, month) by delta months and return normalized (year, month)."""
    total = (year * 12 + (month - 1)) + delta
    return total // 12, (total % 12) + 1


# ───────────────────────────── Test Classes ───────────────────────────── #

class TestBalanceMechanics:
    def test_update_balances_calculates_totals_and_closing(self, user):
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
        assert stmt.closing_balance == -8_000  # 10_000 + 12_000 - 30_000

    def test_update_balances_no_lines_keeps_opening_as_closing(self, user):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT, opening_balance=123_456
        )
        stmt.update_balances()
        stmt.refresh_from_db()
        assert stmt.total_debit == 0
        assert stmt.total_credit == 0
        assert stmt.closing_balance == 123_456


class TestManagerGetOrCreateCurrent:
    def test_creates_and_reuses(self, user):
        stmt1, created1 = Statement.objects.get_or_create_current_statement(
            user
        )
        stmt2, created2 = Statement.objects.get_or_create_current_statement(
            user
        )
        assert created1 is True and created2 is False
        assert stmt1.id == stmt2.id
        today = JalaliDate.today()
        assert (stmt1.year, stmt1.month) == (today.year, today.month)
        assert stmt1.status == StatementStatus.CURRENT


class TestClosingStatement:
    def test_sets_pending_and_due_date(
            self, user, active_credit_limit_factory
    ):
        active_credit_limit_factory(user=user, grace_days=10)
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        before = timezone.now()
        stmt.close_statement()
        after = timezone.now()
        stmt.refresh_from_db()
        assert stmt.status == StatementStatus.PENDING_PAYMENT
        assert stmt.closed_at is not None and before <= stmt.closed_at <= after
        assert stmt.due_date is not None and (
                stmt.due_date - stmt.closed_at).days == 10

    def test_is_noop_when_not_current(self, user):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.PENDING_PAYMENT
        )
        stmt.close_statement()
        stmt.refresh_from_db()
        assert stmt.status == StatementStatus.PENDING_PAYMENT

    def test_recomputes_balances_before_closing(
            self, user, active_credit_limit_factory
    ):
        active_credit_limit_factory(user=user, grace_days=1)
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT, opening_balance=0
        )
        stmt.add_line(StatementLineType.PURCHASE, 50_000)
        stmt.add_line(StatementLineType.PAYMENT, 10_000)
        stmt.close_statement()
        stmt.refresh_from_db()
        assert stmt.status == StatementStatus.PENDING_PAYMENT
        assert stmt.closing_balance == -40_000

    def test_without_credit_limit_sets_due_now(self, user):
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


class TestIsWithinDue:
    def test_true_false_none(self, user):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.PENDING_PAYMENT
        )
        now = timezone.now()
        stmt.due_date = now + timedelta(days=2)
        assert stmt.is_within_due(now=now) is True
        stmt.due_date = now - timedelta(days=1)
        assert stmt.is_within_due(now=now) is False
        stmt.due_date = None
        assert stmt.is_within_due(now=now) is False

    def test_uses_default_now(self, user):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.PENDING_PAYMENT,
            due_date=timezone.now() + timedelta(seconds=1),
        )
        assert stmt.is_within_due() is True

    def test_is_inclusive_at_boundary(self, user):
        """If now == due_date, still within due."""
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.PENDING_PAYMENT
        )
        now = timezone.now()
        stmt.due_date = now
        assert stmt.is_within_due(now=now) is True


class TestMinimumPayment:
    def test_threshold_and_percentage(self, user):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.PENDING_PAYMENT
        )
        stmt.closing_balance = -(MINIMUM_PAYMENT_THRESHOLD - 1)
        assert stmt.calculate_minimum_payment_amount() == 0
        stmt.closing_balance = -MINIMUM_PAYMENT_THRESHOLD
        assert stmt.calculate_minimum_payment_amount() == int(
            MINIMUM_PAYMENT_THRESHOLD * MINIMUM_PAYMENT_PERCENTAGE
        )
        stmt.closing_balance = -1_000_000
        assert stmt.calculate_minimum_payment_amount() == int(
            1_000_000 * MINIMUM_PAYMENT_PERCENTAGE
        )

    @pytest.mark.parametrize(
        "status,closing,expected",
        [
            (StatementStatus.CURRENT, -100_000, 0),
            (StatementStatus.PENDING_PAYMENT, 100_000, 0),
        ],
    )
    def test_zero_when_not_pending_or_non_negative(
            self, user, status, closing, expected
    ):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month, status=status,
            closing_balance=closing
        )
        assert stmt.calculate_minimum_payment_amount() == expected


class TestDueWindowOutcome:
    def test_no_penalty_when_enough_payment(self, user):
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
        assert outcome == StatementStatus.CLOSED_NO_PENALTY and stmt.closed_at is not None

    def test_with_penalty_when_insufficient_payment(self, user):
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
        assert outcome == StatementStatus.CLOSED_WITH_PENALTY and stmt.closed_at is not None

    def test_below_threshold_closes_without_penalty(self, user):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.PENDING_PAYMENT,
            closing_balance=-(MINIMUM_PAYMENT_THRESHOLD - 1),
        )
        assert stmt.determine_due_outcome(
            total_payments_during_due=0
        ) == StatementStatus.CLOSED_NO_PENALTY

    def test_raises_on_non_pending(self, user):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        with pytest.raises(ValueError):
            stmt.determine_due_outcome(total_payments_during_due=0)


class TestPenaltyComputation:
    def test_respects_rate_and_cap(self, user):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.PENDING_PAYMENT
        )
        stmt.closing_balance = -2_000_000
        stmt.due_date = timezone.now() - timedelta(days=5)
        expected = int(2_000_000 * STATEMENT_PENALTY_RATE * 5)
        cap = int(2_000_000 * STATEMENT_MAX_PENALTY_RATE)
        computed = stmt.compute_penalty_amount()
        assert computed == min(expected, cap)

    def test_zero_when_not_pending_or_not_past_due_or_non_negative(self, user):
        today = JalaliDate.today()
        y0, m0 = today.year, today.month
        y1, m1 = _shift_month(y0, m0, -1)
        y2, m2 = _shift_month(y0, m0, -2)
        y3, m3 = _shift_month(y0, m0, -3)
        s1 = Statement.objects.create(
            user=user, year=y0, month=m0, status=StatementStatus.CURRENT,
            closing_balance=-1,
            due_date=timezone.now() - timedelta(days=1),
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
            due_date=timezone.now() - timedelta(days=1),
        )
        assert s3.compute_penalty_amount() == 0
        s4 = Statement.objects.create(
            user=user, year=y3, month=m3,
            status=StatementStatus.PENDING_PAYMENT, closing_balance=-1000,
            due_date=timezone.now() + timedelta(days=1),
        )
        assert s4.compute_penalty_amount() == 0

    def test_uses_explicit_now(self, user):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.PENDING_PAYMENT
        )
        stmt.closing_balance = -1_000_000
        base_due = timezone.now()
        stmt.due_date = base_due
        custom_now = base_due + timedelta(days=3)
        expected_raw = int(1_000_000 * STATEMENT_PENALTY_RATE * 3)
        cap = int(1_000_000 * STATEMENT_MAX_PENALTY_RATE)
        assert stmt.compute_penalty_amount(now=custom_now) == min(
            expected_raw, cap
        )


class TestInterestCarryOverHelper:
    def test_adds_line_only_on_negative_and_current(self, user):
        today = JalaliDate.today()
        cy, cm = today.year, today.month
        current_stmt = Statement.objects.create(
            user=user, year=cy, month=cm, status=StatementStatus.CURRENT
        )
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
        py2, pm2 = _shift_month(cy, cm, -2)
        prev_nonneg = Statement.objects.create(
            user=user, year=py2, month=pm2,
            status=StatementStatus.PENDING_PAYMENT, closing_balance=0
        )
        current_stmt.add_monthly_interest_on_carryover(prev_nonneg)
        assert current_stmt.lines.filter(
            type=StatementLineType.INTEREST
        ).count() == 1  # unchanged
        ny, nm = _shift_month(cy, cm, +1)
        non_current = Statement.objects.create(
            user=user, year=ny, month=nm,
            status=StatementStatus.PENDING_PAYMENT
        )
        with pytest.raises(ValueError):
            non_current.add_monthly_interest_on_carryover(prev_neg)

    def test_duplicate_interest_raises(self, user):
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
        current_stmt.add_monthly_interest_on_carryover(prev_neg_1)
        py2, pm2 = _shift_month(cy, cm, -2)
        prev_neg_2 = Statement.objects.create(
            user=user, year=py2, month=pm2,
            status=StatementStatus.PENDING_PAYMENT, closing_balance=-50_000
        )
        with pytest.raises((ValidationError, IntegrityError)) as exc:
            current_stmt.add_monthly_interest_on_carryover(prev_neg_2)
        assert "uniq_interest_per_statement" in str(exc.value)


class TestReferenceCode:
    def test_is_generated(self, user):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        assert stmt.reference_code is not None

    def test_retries_on_collision(self, monkeypatch, user):
        today = JalaliDate.today()
        py, pm = _shift_month(today.year, today.month, -1)
        Statement.objects.create(
            user=user, year=py, month=pm, status=StatementStatus.CURRENT,
            reference_code="ST-DUP"
        )
        from credit.models import statement as st_mod
        calls = {"n": 0}

        def fake_gen(prefix="ST"):
            calls["n"] += 1
            return "ST-DUP" if calls["n"] == 1 else "ST-UNIQ"

        monkeypatch.setattr(st_mod, "generate_reference_code", fake_gen)
        obj = Statement(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        obj.save()
        assert obj.reference_code == "ST-UNIQ"

    def test_five_collisions_then_null(self, monkeypatch, user):
        from credit.models import statement as st_mod
        def dup_gen(prefix="ST"): return "ST-DUP"

        monkeypatch.setattr(st_mod, "generate_reference_code", dup_gen)
        today = JalaliDate.today()
        py, pm = _shift_month(today.year, today.month, -1)
        Statement.objects.create(
            user=user, year=py, month=pm, status=StatementStatus.CURRENT,
            reference_code="ST-DUP"
        )
        obj = Statement(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        obj.save()
        assert obj.reference_code is None


class TestAddPayment:
    def test_success_creates_positive_payment_line(self, user):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT, opening_balance=0
        )
        stmt.add_payment(5_000, description="Pay")
        stmt.refresh_from_db()
        assert stmt.lines.filter(
            type=StatementLineType.PAYMENT, amount=5_000
        ).count() == 1
        assert stmt.closing_balance == 5_000

    def test_raises_on_zero_amount(self, user):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        with pytest.raises(ValueError):
            stmt.add_payment(0)

    def test_raises_on_non_current(self, user):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.PENDING_PAYMENT
        )
        with pytest.raises(ValueError):
            stmt.add_payment(1000)

    def test_accepts_negative_and_normalizes_to_positive(self, user):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT, opening_balance=0
        )
        stmt.add_payment(-3_000, description="neg")
        stmt.refresh_from_db()
        assert stmt.lines.filter(
            type=StatementLineType.PAYMENT, amount=3_000
        ).count() == 1
        assert stmt.closing_balance == 3_000


class TestAddPurchase:
    """Validations and happy-path for add_purchase()"""

    @staticmethod
    def _make_dummy_tx(user_id, amount, status_ok=True, belong="from"):
        """Minimal in-memory transaction stub (no DB row)."""

        class _W:
            def __init__(self, uid): self.user_id = uid

        class _T: pass

        from wallets.utils.choices import TransactionStatus
        t = _T()
        t.amount = amount
        t.status = TransactionStatus.SUCCESS if status_ok else "NOT_SUCCESS"
        t.from_wallet = _W(user_id if belong in ("from", "both") else 999_001)
        t.to_wallet = _W(user_id if belong in ("to", "both") else 999_002)
        return t

    @staticmethod
    def _stub_credit_limit(is_active=True, days_ahead=10, available=1_000_000):
        class _CL:
            def __init__(self):
                self.is_active = is_active
                self.expiry_date = timezone.localdate() + timezone.timedelta(
                    days=days_ahead
                )
                self.available_limit = available

        return _CL()

    def test_raises_on_non_current(self, user, monkeypatch):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.PENDING_PAYMENT
        )
        from credit.models.credit_limit import CreditLimit
        monkeypatch.setattr(
            CreditLimit.objects, "get_user_credit_limit",
            lambda u: self._stub_credit_limit()
        )
        with pytest.raises(ValueError):
            stmt.add_purchase(
                self._make_dummy_tx(
                    user.id, 10_000, status_ok=True, belong="both"
                )
            )

    def test_raises_on_non_success_tx(self, user, monkeypatch):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        from credit.models.credit_limit import CreditLimit
        monkeypatch.setattr(
            CreditLimit.objects, "get_user_credit_limit",
            lambda u: self._stub_credit_limit()
        )
        with pytest.raises(ValueError):
            stmt.add_purchase(
                self._make_dummy_tx(
                    user.id, 10_000, status_ok=False, belong="both"
                )
            )

    def test_raises_when_tx_not_belongs_to_user(self, user, monkeypatch):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        from credit.models.credit_limit import CreditLimit
        monkeypatch.setattr(
            CreditLimit.objects, "get_user_credit_limit",
            lambda u: self._stub_credit_limit()
        )
        with pytest.raises(ValueError):
            stmt.add_purchase(
                self._make_dummy_tx(
                    user.id, 10_000, status_ok=True, belong="none"
                )
            )

    def test_raises_without_active_credit_limit(self, user, monkeypatch):
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
                self._make_dummy_tx(
                    user.id, 10_000, status_ok=True, belong="both"
                )
            )

    @pytest.mark.parametrize("is_active,days_ahead", [(False, 10), (True, 0)])
    def test_raises_on_inactive_or_expired_limit(
            self, user, monkeypatch, is_active, days_ahead
    ):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        from credit.models.credit_limit import CreditLimit
        monkeypatch.setattr(
            CreditLimit.objects, "get_user_credit_limit",
            lambda u: self._stub_credit_limit(
                is_active=is_active, days_ahead=days_ahead
            ),
        )
        with pytest.raises(ValueError):
            stmt.add_purchase(
                self._make_dummy_tx(
                    user.id, 10_000, status_ok=True, belong="both"
                )
            )

    def test_raises_on_insufficient_available_limit(self, user, monkeypatch):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        from credit.models.credit_limit import CreditLimit
        monkeypatch.setattr(
            CreditLimit.objects, "get_user_credit_limit",
            lambda u: self._stub_credit_limit(available=5_000)
        )
        with pytest.raises(ValueError):
            stmt.add_purchase(
                self._make_dummy_tx(
                    user.id, 10_001, status_ok=True, belong="both"
                )
            )

    def test_success_calls_add_line_with_abs_amount(self, user, monkeypatch):
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        from credit.models.credit_limit import CreditLimit
        monkeypatch.setattr(
            CreditLimit.objects, "get_user_credit_limit",
            lambda u: self._stub_credit_limit(
                available=999_999
            )
        )
        called = {}

        def fake_add_line(
                self, type_, amount, transaction=None, description=""
        ):
            called["type"] = type_;
            called["amount"] = amount
            called["transaction"] = transaction;
            called["description"] = description

        monkeypatch.setattr(
            Statement, "add_line", fake_add_line, raising=False
        )
        trx = self._make_dummy_tx(
            user.id, amount=12_345, status_ok=True, belong="both"
        )
        stmt.add_purchase(trx, description="Shop A")
        assert called["type"] == StatementLineType.PURCHASE
        assert called["amount"] == 12_345
        assert called["transaction"] == trx
        assert called["description"] == "Shop A"


class TestManagerCloseMonthlyStatements:
    def test_no_currents_returns_zero(self):
        result = Statement.objects.close_monthly_statements()
        assert result == {
            "statements_closed": 0, "statements_created": 0,
            "interest_lines_added": 0
        }
