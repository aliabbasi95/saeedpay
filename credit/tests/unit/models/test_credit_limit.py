import pytest
from django.db import IntegrityError
from django.utils import timezone
from persiantools.jdatetime import JalaliDate

from credit.models.credit_limit import CreditLimit
from credit.models.statement import Statement
from credit.utils.choices import StatementLineType, StatementStatus

pytestmark = pytest.mark.django_db


# ───────────────────────────── Helpers ───────────────────────────── #

def _prev_jalali_year_month():
    """Return (year, month) for the previous Jalali month."""
    today = JalaliDate.today()
    return (today.year, today.month - 1) if today.month > 1 else (
        today.year - 1, 12)


# ───────────────────────────── Test Classes ───────────────────────────── #

class TestGetUserCreditLimit:
    """Manager: get_user_credit_limit"""

    def test_returns_active_non_expired(
            self, user, active_credit_limit_factory
    ):
        active = active_credit_limit_factory(
            user=user, is_active=True,
            expiry_date=timezone.localdate() + timezone.timedelta(days=1),
        )
        got = CreditLimit.objects.get_user_credit_limit(user)
        assert got == active

    def test_ignores_expired(self, user, active_credit_limit_factory):
        active_credit_limit_factory(
            user=user, is_active=True,
            expiry_date=timezone.localdate() - timezone.timedelta(days=1),
        )
        assert CreditLimit.objects.get_user_credit_limit(user) is None

    def test_excludes_expiring_today(self, user, active_credit_limit_factory):
        active_credit_limit_factory(user=user, is_active=True, expiry_days=0)
        assert CreditLimit.objects.get_user_credit_limit(user) is None


class TestGetAvailableCredit:
    """Manager: get_available_credit"""

    def test_no_limit_returns_zero(self, user):
        assert CreditLimit.objects.get_available_credit(user) == 0

    def test_matches_property_value(
            self, user, active_credit_limit_factory, current_statement_factory
    ):
        limit = active_credit_limit_factory(
            user=user, approved_limit=1_000_000, is_active=True,
            expiry_date=timezone.localdate() + timezone.timedelta(days=10),
        )
        stmt = current_statement_factory(user=user, opening_balance=0)
        stmt.add_line(StatementLineType.PURCHASE, 150_000)
        stmt.refresh_from_db()
        assert CreditLimit.objects.get_available_credit(
            user
        ) == limit.available_limit == 850_000


class TestAvailableLimitProperty:
    """CreditLimit.available_limit behavior"""

    def test_uses_only_current_ignores_pending(
            self, user, active_credit_limit_factory
    ):
        limit = active_credit_limit_factory(
            user=user, approved_limit=500_000, is_active=True,
            expiry_date=timezone.localdate() + timezone.timedelta(days=5),
        )
        y, m = _prev_jalali_year_month()
        Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.PENDING_PAYMENT,
            opening_balance=0, closing_balance=-400_000,
            total_debit=400_000, total_credit=0,
            due_date=timezone.localtime(timezone.now()) + timezone.timedelta(
                days=3
                ),
        )
        assert limit.available_limit == 500_000

    def test_clamped_to_zero_when_carryover_exceeds_limit(
            self, user, active_credit_limit_factory, current_statement_factory
    ):
        limit = active_credit_limit_factory(
            user=user, approved_limit=100_000, is_active=True,
            expiry_date=timezone.localdate() + timezone.timedelta(days=5),
        )
        stmt = current_statement_factory(user=user, opening_balance=-200_000)
        stmt.refresh_from_db()
        assert stmt.status == StatementStatus.CURRENT
        assert stmt.closing_balance == -200_000
        assert limit.available_limit == 0

    def test_full_when_no_current_statements(
            self, user, active_credit_limit_factory
    ):
        limit = active_credit_limit_factory(
            user=user, approved_limit=750_000, is_active=True,
            expiry_date=timezone.localdate() + timezone.timedelta(days=10),
        )
        assert limit.available_limit == 750_000

    def test_not_exceed_approved_on_net_positive_current(
            self, user, active_credit_limit_factory, current_statement_factory
    ):
        limit = active_credit_limit_factory(
            user=user, approved_limit=500_000, is_active=True,
            expiry_date=timezone.localdate() + timezone.timedelta(days=10),
        )
        stmt = current_statement_factory(user=user, opening_balance=0)
        stmt.add_line(StatementLineType.PURCHASE, 100_000)
        stmt.add_line(StatementLineType.PAYMENT, 150_000)
        stmt.refresh_from_db()
        assert limit.available_limit == 500_000  # clamp to approved_limit


class TestGraceDays:
    """grace_days property"""

    def test_override(self, user, active_credit_limit_factory):
        limit = active_credit_limit_factory(user=user, grace_days=7)
        assert limit.grace_days == 7

    def test_default_follows_settings(
            self, monkeypatch, user, active_credit_limit_factory
    ):
        monkeypatch.setattr(
            'credit.models.credit_limit.STATEMENT_GRACE_DAYS', 15,
            raising=False
        )
        limit = active_credit_limit_factory(user=user, grace_days=None)
        assert limit.grace_days == 15


class TestActivationDeactivation:
    """Activation / Deactivation semantics"""

    def test_activate_keeps_only_one_active(
            self, user, active_credit_limit_factory
    ):
        first = active_credit_limit_factory(
            user=user, is_active=True, approved_limit=1_000_000
        )
        second = active_credit_limit_factory(
            user=user, is_active=False, approved_limit=2_000_000
        )
        second.activate()
        first.refresh_from_db();
        second.refresh_from_db()
        assert second.is_active is True and first.is_active is False
        assert CreditLimit.objects.filter(
            user=user, is_active=True
        ).count() == 1

    def test_deactivate_user_active_limits_bulk(
            self, user, active_credit_limit_factory
    ):
        a = active_credit_limit_factory(user=user, is_active=True)
        active_credit_limit_factory(user=user, is_active=False)
        changed = CreditLimit.deactivate_user_active_limits(user)
        assert changed in (0, 1)
        a.refresh_from_db()
        assert a.is_active is False
        assert CreditLimit.objects.filter(
            user=user, is_active=True
        ).count() == 0


class TestDBConstraintsAndReferenceCode:
    """DB constraints & reference_code generation"""

    def test_unique_active_per_user(self, user, active_credit_limit_factory):
        active_credit_limit_factory(user=user, is_active=True)
        with pytest.raises(IntegrityError):
            CreditLimit.objects.create(
                user=user, approved_limit=123_456, is_active=True,
                expiry_date=timezone.localdate() + timezone.timedelta(days=10),
            )

    def test_reference_code_is_generated(
            self, user, active_credit_limit_factory
    ):
        limit = active_credit_limit_factory(user=user, is_active=False)
        assert limit.reference_code
        assert CreditLimit.objects.exclude(reference_code=None).count() == 1

    def test_reference_code_retries_on_collision(self, monkeypatch, user):
        from credit.models import credit_limit as cl_mod
        CreditLimit.objects.create(
            user=user, approved_limit=111, is_active=False,
            expiry_date=timezone.localdate() + timezone.timedelta(days=1),
            reference_code="CR-DUP",
        )
        calls = {"n": 0}

        def fake_gen(prefix="CR"):
            calls["n"] += 1
            return "CR-DUP" if calls["n"] == 1 else "CR-UNIQ"

        monkeypatch.setattr(cl_mod, "generate_reference_code", fake_gen)
        obj = CreditLimit(
            user=user, approved_limit=222, is_active=False,
            expiry_date=timezone.localdate() + timezone.timedelta(days=2),
        )
        obj.save()
        assert obj.reference_code == "CR-UNIQ"

    def test_reference_code_five_collisions_then_null(self, monkeypatch, user):
        from credit.models import credit_limit as cl_mod
        def dup_gen(prefix="CR"): return "CR-DUP"

        monkeypatch.setattr(cl_mod, "generate_reference_code", dup_gen)
        CreditLimit.objects.create(
            user=user, approved_limit=1, is_active=False,
            expiry_date=timezone.localdate() + timezone.timedelta(days=1),
            reference_code="CR-DUP",
        )
        obj = CreditLimit(
            user=user, approved_limit=2, is_active=False,
            expiry_date=timezone.localdate() + timezone.timedelta(days=2),
        )
        obj.save()
        assert obj.reference_code is None  # fell back to NULL after collisions


class TestStr:
    """__str__ should be human-readable"""

    def test_contains_user_and_formatted_amount(
            self, user, active_credit_limit_factory
    ):
        limit = active_credit_limit_factory(
            user=user, approved_limit=1_234_567, is_active=False
        )
        s = str(limit)
        assert (user.username in s) or (str(user.id) in s)
        assert "1,234,567" in s and "ریال" in s


class TestEndToEndAvailableLimit:
    """Sanity flow: purchase and payment affect available_limit"""

    def test_reflects_purchase_and_payment(
            self, user, active_credit_limit_factory, current_statement_factory
    ):
        limit = active_credit_limit_factory(
            user=user, approved_limit=1_000_000, is_active=True
        )
        stmt = current_statement_factory(user=user, opening_balance=0)
        stmt.add_line(StatementLineType.PURCHASE, 200_000)
        stmt.add_line(StatementLineType.PAYMENT, 50_000)
        stmt.refresh_from_db()
        assert limit.available_limit == 850_000
