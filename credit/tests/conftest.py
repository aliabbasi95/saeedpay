# tests/conftest.py

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from persiantools.jdatetime import JalaliDate

from credit.models.credit_limit import CreditLimit
from credit.models.statement import Statement
from credit.utils.choices import StatementStatus

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
        exp_date = expiry_date or (timezone.localdate() + timedelta(days=expiry_days))
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
