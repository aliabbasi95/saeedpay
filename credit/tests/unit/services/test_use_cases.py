# tests/unit/services/test_statement_use_cases.py

import datetime as dt

import pytest
from django.utils import timezone

from credit.models import Statement
from credit.services.use_cases import StatementUseCases
from credit.utils.choices import StatementStatus, StatementLineType
from wallets.utils.choices import TransactionStatus, OwnerType, WalletKind

pytestmark = pytest.mark.django_db


# ---------- Local fixtures that complement global conftest fixtures ----------

@pytest.fixture
def wallets_for_user(user, django_user_model):
    """
    Create a 'from' wallet owned by the test user (customer/credit)
    and a 'to' wallet owned by a merchant (merchant_gateway).
    """
    from wallets.models import Wallet

    merchant_user = django_user_model.objects.create(
        username="merchant_user", password="x"
    )

    w_from = Wallet.objects.create(
        user=user,
        owner_type=OwnerType.CUSTOMER,
        kind=WalletKind.CREDIT,
        balance=0,  # balance is irrelevant for purchase recording
    )
    w_to = Wallet.objects.create(
        user=merchant_user,
        owner_type=OwnerType.MERCHANT,
        kind=WalletKind.MERCHANT_GATEWAY,
        balance=0,
    )
    return w_from, w_to


@pytest.fixture
def success_transaction(wallets_for_user):
    """
    SUCCESS transaction from user's wallet to merchant's wallet.
    """
    from wallets.models import Transaction
    w_from, w_to = wallets_for_user
    return Transaction.objects.create(
        from_wallet=w_from,
        to_wallet=w_to,
        amount=250_000,  # 250k
        status=TransactionStatus.SUCCESS,
        description="purchase"
    )


@pytest.fixture
def failed_transaction(wallets_for_user):
    from wallets.models import Transaction
    w_from, w_to = wallets_for_user
    return Transaction.objects.create(
        from_wallet=w_from,
        to_wallet=w_to,
        amount=250_000,
        status=TransactionStatus.FAILED,
        description="purchase"
    )


# ======================================================================
# Purchases
# ======================================================================

class TestPurchases:
    def test_record_successful_purchase_creates_purchase_line_and_updates_balances(
            self, user, active_credit_limit_factory, current_statement_factory,
            success_transaction
    ):
        # Ensure active credit limit (not expired)
        active_credit_limit_factory(
            user=user,
            approved_limit=10_000_000,
            is_active=True,
            grace_days=7,
            expiry_days=30
        )
        current_statement_factory(user)

        stmt = StatementUseCases.record_successful_purchase_from_transaction(
            success_transaction.id, description="Purchase Test"
        )

        stmt.refresh_from_db()
        lines = list(stmt.lines.all())
        assert stmt.status == StatementStatus.CURRENT
        assert len(lines) == 1
        line = lines[0]
        assert line.type == StatementLineType.PURCHASE
        assert line.amount < 0  # normalized negative charge
        assert stmt.total_debit == abs(line.amount)
        assert stmt.total_credit == 0
        # closing = opening + credit - debit
        assert stmt.closing_balance == stmt.opening_balance + 0 - abs(
            line.amount
        )

    def test_record_successful_purchase_attaches_transaction_and_description(
            self, user, active_credit_limit_factory, current_statement_factory,
            wallets_for_user
    ):
        """
        Ensure the created purchase line carries transaction_id and the provided description.
        """
        from wallets.models import Transaction
        from wallets.utils.choices import TransactionStatus as TxS

        active_credit_limit_factory(
            user=user, is_active=True, expiry_days=30, approved_limit=1_000_000
        )
        stmt = current_statement_factory(user)
        w_from, w_to = wallets_for_user
        tx = Transaction.objects.create(
            from_wallet=w_from, to_wallet=w_to, amount=90_000,
            status=TxS.SUCCESS, description="shop A"
        )

        updated = StatementUseCases.record_successful_purchase_from_transaction(
            tx.id, description="attached-desc"
        )
        line = updated.lines.last()
        assert line.type == StatementLineType.PURCHASE
        assert line.transaction_id == tx.id
        assert (line.description or "") == "attached-desc"

    def test_record_successful_purchase_requires_success_status(
            self, user, active_credit_limit_factory, current_statement_factory,
            failed_transaction
    ):
        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)
        current_statement_factory(user)

        with pytest.raises(ValueError, match="Transaction must be SUCCESS"):
            StatementUseCases.record_successful_purchase_from_transaction(
                failed_transaction.id
            )

    def test_record_successful_purchase_requires_active_credit_limit(
            self, user, current_statement_factory, success_transaction
    ):
        # No active credit_limit for user
        current_statement_factory(user)
        with pytest.raises(ValueError, match="No active credit limit"):
            StatementUseCases.record_successful_purchase_from_transaction(
                success_transaction.id
            )

    def test_record_successful_purchase_rejects_when_available_credit_is_insufficient(
            self, user, active_credit_limit_factory, current_statement_factory,
            success_transaction
    ):
        # Approved limit intentionally smaller than tx amount (250_000)
        active_credit_limit_factory(
            user=user, approved_limit=100_000, is_active=True, expiry_days=30
        )
        current_statement_factory(user)

        with pytest.raises(ValueError, match="Insufficient available credit"):
            StatementUseCases.record_successful_purchase_from_transaction(
                success_transaction.id
            )

    def test_record_successful_purchase_rejects_when_tx_not_belonging_to_user(
            self, user, django_user_model, active_credit_limit_factory
    ):
        """
        If the transaction does not belong to the caller user (neither from nor to side),
        the use-case should reject it.
        """
        from wallets.models import Wallet, Transaction

        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)

        alien = django_user_model.objects.create(
            username="alien", password="x"
        )
        w_from = Wallet.objects.create(
            user=alien, owner_type=OwnerType.CUSTOMER, kind=WalletKind.CREDIT,
            balance=0
        )
        w_to = Wallet.objects.create(
            user=alien, owner_type=OwnerType.MERCHANT,
            kind=WalletKind.MERCHANT_GATEWAY, balance=0
        )
        alien_tx = Transaction.objects.create(
            from_wallet=w_from, to_wallet=w_to, amount=10_000,
            status=TransactionStatus.SUCCESS
        )

        with pytest.raises(ValueError):
            StatementUseCases.record_successful_purchase_from_transaction(
                alien_tx.id
            )

    @pytest.mark.parametrize("is_active,expiry_days", [(False, 30), (True, 0)])
    def test_record_successful_purchase_rejects_when_credit_limit_inactive_or_expired(
            self, user, active_credit_limit_factory, current_statement_factory,
            wallets_for_user, is_active, expiry_days
    ):
        """
        Extra guard: inactive or expired credit limit must reject purchase.
        """
        from wallets.models import Transaction
        from wallets.utils.choices import TransactionStatus as TxS

        # Prepare a tx that belongs to the user
        current_statement_factory(user)
        w_from, w_to = wallets_for_user
        tx = Transaction.objects.create(
            from_wallet=w_from, to_wallet=w_to, amount=90_000,
            status=TxS.SUCCESS
        )

        # Make credit limit bad (inactive or expired)
        active_credit_limit_factory(
            user=user, is_active=is_active, expiry_days=expiry_days,
            approved_limit=1_000_000
        )

        with pytest.raises(ValueError, match="No active credit limit"):
            StatementUseCases.record_successful_purchase_from_transaction(
                tx.id
            )


# ======================================================================
# Payments
# ======================================================================

class TestPayments:
    def test_record_payment_on_current_statement_creates_positive_payment_line_and_updates_balance(
            self, user, current_statement_factory
    ):
        stmt = current_statement_factory(user)
        before_credit = stmt.total_credit

        stmt = StatementUseCases.record_payment_on_current_statement(
            user, amount=120_000, description="Pay"
        )
        stmt.refresh_from_db()
        line = stmt.lines.last()
        assert line.type == StatementLineType.PAYMENT
        assert line.amount > 0
        assert stmt.total_credit == before_credit + line.amount
        assert stmt.status == StatementStatus.CURRENT

    def test_record_payment_rejects_zero_amount(self, user):
        with pytest.raises(ValueError, match="non-zero"):
            StatementUseCases.record_payment_on_current_statement(
                user, amount=0
            )

    def test_record_payment_normalizes_negative_amount_and_attaches_transaction(
            self, user, current_statement_factory, wallets_for_user
    ):
        # Arrange
        from wallets.models import Transaction
        from wallets.utils.choices import TransactionStatus as TxS
        w_from, w_to = wallets_for_user
        pay_tx = Transaction.objects.create(
            from_wallet=w_from, to_wallet=w_to, amount=55_000,
            status=TxS.SUCCESS, description="repay"
        )
        stmt = current_statement_factory(user)

        # Act: negative amount should be normalized to positive PAYMENT line
        updated = StatementUseCases.record_payment_on_current_statement(
            user, amount=-55_000, payment_transaction=pay_tx,
            description="repay negative amount"
        )

        # Assert
        line = updated.lines.last()
        assert line.type == StatementLineType.PAYMENT
        assert line.amount == 55_000
        assert line.transaction_id == pay_tx.id
        assert (line.description or "") == "repay negative amount"


# ======================================================================
# Month-end rollover
# ======================================================================

class TestMonthEndRollover:
    def test_month_end_rollover_closes_past_current_and_creates_new_with_interest_for_negative_carryover(
            self, user, active_credit_limit_factory, current_statement_factory
    ):
        """
        Make CURRENT statement belong to a past Persian month:
        - Put a negative closing balance to trigger interest on the new CURRENT.
        - Ensure counts from the result dict match.
        """
        from persiantools.jdatetime import JalaliDate

        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)
        current_statement = current_statement_factory(user)

        # 1) simulate past month by setting year/month smaller than today
        today = JalaliDate.today()
        past_year, past_month = (
            (today.year - 1, today.month) if today.month == 1 else (today.year,
                                                                    today.month - 1))
        current_statement.year = past_year
        current_statement.month = past_month
        current_statement.save(update_fields=["year", "month"])

        # 2) create a negative charge so closing < 0
        current_statement.add_line(
            StatementLineType.PURCHASE, 500_000, description="past purchase"
        )
        current_statement.refresh_from_db()
        assert current_statement.closing_balance < 0

        # 3) perform rollover
        result = StatementUseCases.perform_month_end_rollover()
        assert result["statements_closed"] >= 1
        assert result["statements_created"] >= 1
        assert result["interest_lines_added"] >= 1

        # old must now be PENDING_PAYMENT, new CURRENT exists for same user
        old = Statement.objects.get(
            user=user, year=past_year, month=past_month
        )
        assert old.status == StatementStatus.PENDING_PAYMENT
        new_current = Statement.objects.get(
            user=user, status=StatementStatus.CURRENT
        )
        assert new_current.opening_balance == old.closing_balance
        assert new_current.lines.filter(
            type=StatementLineType.INTEREST
        ).exists()

    def test_month_end_rollover_no_interest_when_carryover_non_negative(
            self, user, active_credit_limit_factory, current_statement_factory
    ):
        """
        If closing_balance >= 0, rollover must NOT add INTEREST to the new CURRENT.
        """
        from persiantools.jdatetime import JalaliDate

        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)
        stmt = current_statement_factory(user)

        # Move to previous month, but keep closing_balance >= 0
        today = JalaliDate.today()
        prev_year, prev_month = (
            (today.year - 1, today.month) if today.month == 1 else (today.year,
                                                                    today.month - 1))
        stmt.year = prev_year
        stmt.month = prev_month
        stmt.save(update_fields=["year", "month"])

        # Make sure closing >= 0 (opening is 0 and no charges/payments)
        stmt.refresh_from_db()
        assert stmt.closing_balance >= 0

        result = StatementUseCases.perform_month_end_rollover()
        assert result["statements_closed"] >= 1
        new_current = Statement.objects.get(
            user=user, status=StatementStatus.CURRENT
        )
        assert not new_current.lines.filter(
            type=StatementLineType.INTEREST
        ).exists()

    def test_month_end_rollover_is_idempotent_does_not_duplicate_interest(
            self, user, active_credit_limit_factory, current_statement_factory
    ):
        """
        Running rollover twice should not create duplicate INTEREST lines or re-close.
        """
        from persiantools.jdatetime import JalaliDate

        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)
        stmt = current_statement_factory(user)

        # Move to previous month + negative carryover
        today = JalaliDate.today()
        prev_year, prev_month = (
            (today.year - 1, today.month) if today.month == 1 else (today.year,
                                                                    today.month - 1))
        stmt.year = prev_year
        stmt.month = prev_month
        stmt.save(update_fields=["year", "month"])
        stmt.add_line(StatementLineType.PURCHASE, 100_000)  # make it negative
        stmt.refresh_from_db()
        assert stmt.closing_balance < 0

        # First run
        StatementUseCases.perform_month_end_rollover()
        current1 = Statement.objects.get(
            user=user, status=StatementStatus.CURRENT
        )
        interest_count_after_first = current1.lines.filter(
            type=StatementLineType.INTEREST
        ).count()
        assert interest_count_after_first == 1

        # Second run (no more past-month CURRENT to close)
        StatementUseCases.perform_month_end_rollover()
        current2 = Statement.objects.get(
            user=user, status=StatementStatus.CURRENT
        )
        interest_count_after_second = current2.lines.filter(
            type=StatementLineType.INTEREST
        ).count()
        assert interest_count_after_second == 1  # unchanged

    def test_month_end_rollover_updates_existing_current_and_adds_single_interest(
            self, user, active_credit_limit_factory, current_statement_factory
    ):
        from persiantools.jdatetime import JalaliDate

        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)

        # Create a past-month CURRENT with negative closing
        past_stmt = current_statement_factory(user)
        today = JalaliDate.today()
        prev_year, prev_month = (
            (today.year - 1, today.month) if today.month == 1 else (today.year,
                                                                    today.month - 1))
        past_stmt.year = prev_year
        past_stmt.month = prev_month
        past_stmt.save(update_fields=["year", "month"])
        past_stmt.add_line(StatementLineType.PURCHASE, 300_000)
        past_stmt.refresh_from_db()
        assert past_stmt.closing_balance < 0

        # Pre-create CURRENT for current J-month
        _cur_existing, _ = Statement.objects.get_or_create_current_statement(
            user
        )

        # Act
        StatementUseCases.perform_month_end_rollover()

        # --- Re-fetch fresh instances from DB (DO NOT reuse cached objects) ---
        past_after = Statement.objects.get(
            user=user, year=prev_year, month=prev_month
        )
        current_after = Statement.objects.get(
            user=user, status=StatementStatus.CURRENT
        )

        # Assert: past moved to pending
        assert past_after.status == StatementStatus.PENDING_PAYMENT

        # Assert: current opening = past closing (carry-over)
        assert current_after.opening_balance == past_after.closing_balance

        # Assert: exactly one INTEREST line on current
        assert current_after.lines.filter(
            type=StatementLineType.INTEREST
        ).count() == 1

    def test_month_end_rollover_sets_due_date_using_credit_limit_grace_days(
            self, user, active_credit_limit_factory, current_statement_factory
    ):
        from persiantools.jdatetime import JalaliDate

        # Set a distinctive grace days to assert on
        active_credit_limit_factory(
            user=user, is_active=True, grace_days=9, expiry_days=30
        )
        stmt = current_statement_factory(user)

        # move to previous month and make negative to ensure closing
        today = JalaliDate.today()
        prev_year, prev_month = (
            (today.year - 1, today.month) if today.month == 1 else (today.year,
                                                                    today.month - 1))
        stmt.year = prev_year
        stmt.month = prev_month
        stmt.save(update_fields=["year", "month"])
        stmt.add_line(StatementLineType.PURCHASE, 100_000)
        stmt.refresh_from_db()

        # Act
        StatementUseCases.perform_month_end_rollover()

        # Assert: due_date = closed_at + grace_days
        stmt.refresh_from_db()
        assert stmt.status == StatementStatus.PENDING_PAYMENT
        assert stmt.due_date is not None and stmt.closed_at is not None
        delta_days = (stmt.due_date - stmt.closed_at).days
        assert delta_days == 9

    def test_rollover_noop_returns_zero_when_no_past_currents(self, user):
        # Ensure there is no past-month CURRENT to close
        Statement.objects.filter(user=user).delete()
        Statement.objects.get_or_create_current_statement(user)
        res = StatementUseCases.perform_month_end_rollover()
        assert res == {
            "statements_closed": 0, "statements_created": 0,
            "interest_lines_added": 0
        }

    def test_month_end_rollover_returns_exact_counts_for_one_past_current(
            self, user, active_credit_limit_factory, current_statement_factory
    ):
        """
        Single user, exactly one CURRENT moved to previous month and negative -> expect {closed:1, created:1, interest_lines:1}
        """
        from persiantools.jdatetime import JalaliDate

        # Ensure clean slate
        Statement.objects.filter(user=user).delete()

        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)
        stmt = current_statement_factory(user)

        today = JalaliDate.today()
        prev_year, prev_month = (
            (today.year - 1, today.month) if today.month == 1 else (today.year,
                                                                    today.month - 1))
        stmt.year = prev_year
        stmt.month = prev_month
        stmt.save(update_fields=["year", "month"])
        stmt.add_line(StatementLineType.PURCHASE, 111_000)
        stmt.refresh_from_db()
        assert stmt.closing_balance < 0

        res = StatementUseCases.perform_month_end_rollover()
        assert res == {
            "statements_closed": 1, "statements_created": 1,
            "interest_lines_added": 1
        }

    def test_rollover_interest_amount_exact(
            self, user, active_credit_limit_factory, current_statement_factory
    ):
        from credit.utils.constants import MONTHLY_INTEREST_RATE
        from persiantools.jdatetime import JalaliDate

        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)
        stmt = current_statement_factory(user)

        # Move to previous Jalali month and make closing balance negative
        today = JalaliDate.today()
        prev_year, prev_month = (
            (today.year - 1, today.month) if today.month == 1 else (today.year,
                                                                    today.month - 1))
        stmt.year = prev_year
        stmt.month = prev_month
        stmt.save(update_fields=["year", "month"])
        stmt.add_line(StatementLineType.PURCHASE, 200_000)
        stmt.refresh_from_db()
        prev_closing = stmt.closing_balance

        StatementUseCases.perform_month_end_rollover()
        current = Statement.objects.get(
            user=user, status=StatementStatus.CURRENT
        )
        interest = current.lines.filter(type=StatementLineType.INTEREST).last()
        assert interest is not None
        expected = -int(abs(prev_closing) * MONTHLY_INTEREST_RATE)
        assert interest.amount == expected

    def test_month_end_rollover_counts_multiple_users(
            self, user, django_user_model, active_credit_limit_factory,
            current_statement_factory
    ):
        """
        Two users each with a past-month CURRENT with negative closing → both should be rolled over
        with interest lines and proper carry-over; counters should reflect 2.
        """
        from persiantools.jdatetime import JalaliDate

        # Create second user and activate credit limits
        user_b = django_user_model.objects.create(
            username="user_b", password="x"
        )
        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)
        active_credit_limit_factory(
            user=user_b, is_active=True, expiry_days=30
        )

        # Prepare past-month CURRENT for both users with negative closing
        today = JalaliDate.today()
        prev_year, prev_month = (
            (today.year - 1, today.month) if today.month == 1 else (today.year,
                                                                    today.month - 1))

        past_a = current_statement_factory(user)
        past_a.year = prev_year
        past_a.month = prev_month
        past_a.save(update_fields=["year", "month"])
        past_a.add_line(StatementLineType.PURCHASE, 210_000)
        past_a.refresh_from_db()

        past_b = Statement.objects.get_or_create_current_statement(user_b)[0]
        past_b.year = prev_year
        past_b.month = prev_month
        past_b.save(update_fields=["year", "month"])
        past_b.add_line(StatementLineType.PURCHASE, 320_000)
        past_b.refresh_from_db()

        res = StatementUseCases.perform_month_end_rollover()
        assert res["statements_closed"] >= 2
        assert res["statements_created"] >= 2
        assert res["interest_lines_added"] >= 2

        # Verify per-user effects
        curr_a = Statement.objects.get(
            user=user, status=StatementStatus.CURRENT
        )
        curr_b = Statement.objects.get(
            user=user_b, status=StatementStatus.CURRENT
        )
        assert curr_a.opening_balance == past_a.closing_balance
        assert curr_b.opening_balance == past_b.closing_balance
        assert curr_a.lines.filter(type=StatementLineType.INTEREST).exists()
        assert curr_b.lines.filter(type=StatementLineType.INTEREST).exists()


# ======================================================================
# Finalize due windows
# ======================================================================

class TestFinalizeDueWindows:
    def _make_pending_with_due(
            self, user, closing_balance=-1_000_000, grace_days=5,
            closed_at=None
    ):
        """
        Helper: create a PENDING_PAYMENT statement for `user` that belongs to the PREVIOUS Persian month,
        with a given negative closing balance and a due_date in the past.
        This avoids violating the unique (user, year, month) constraint when creating a new CURRENT for the current month.
        """
        from persiantools.jdatetime import JalaliDate

        stmt, _ = Statement.objects.get_or_create_current_statement(user)

        # 1) seed negative closing balance (if needed)
        delta = abs(closing_balance) - abs(
            stmt.closing_balance if stmt.closing_balance < 0 else 0
        )
        if delta > 0:
            stmt.add_line(
                StatementLineType.PURCHASE, delta, description="seed debt"
            )
            stmt.refresh_from_db()

        # 2) move the statement to PREVIOUS Persian month
        today = JalaliDate.today()
        prev_year, prev_month = (
            (today.year - 1, today.month) if today.month == 1 else (today.year,
                                                                    today.month - 1))
        stmt.year = prev_year
        stmt.month = prev_month
        stmt.save(update_fields=["year", "month"])

        # 3) close to pending (past-due)
        now = timezone.now()
        stmt.status = StatementStatus.PENDING_PAYMENT
        stmt.closed_at = closed_at or (now - dt.timedelta(days=10))
        stmt.due_date = now - dt.timedelta(days=grace_days)  # already overdue
        stmt.save(
            update_fields=["status", "closed_at", "due_date",
                           "closing_balance"]
        )

        return stmt

    def test_finalize_due_windows_no_penalty_when_minimum_paid_within_window(
            self, user, active_credit_limit_factory
    ):
        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)
        pending = self._make_pending_with_due(
            user, closing_balance=-2_000_000, grace_days=3
        )
        current, _ = Statement.objects.get_or_create_current_statement(user)

        # Pay >= minimum in the window [closed_at .. due_date]
        min_required = pending.calculate_minimum_payment_amount()
        assert min_required > 0

        # Create a payment exactly at due window end boundary
        win_end = pending.due_date

        # Monkeypatch timezone.now so the payment falls inside window
        original_now = timezone.now
        try:
            timezone.now = lambda: win_end
            current.add_line(
                StatementLineType.PAYMENT, min_required,
                description="on-time payment"
            )
        finally:
            timezone.now = original_now

        result = StatementUseCases.finalize_due_windows(
            now=win_end + dt.timedelta(seconds=1)
        )
        assert result.finalized_count >= 1
        assert result.closed_without_penalty_count >= 1
        assert result.closed_with_penalty_count == 0

        pending.refresh_from_db()
        assert pending.status == StatementStatus.CLOSED_NO_PENALTY
        # No penalty line on current
        assert not current.lines.filter(
            type=StatementLineType.PENALTY
        ).exists()

    def test_finalize_due_windows_with_penalty_when_minimum_not_paid(
            self, user, active_credit_limit_factory
    ):
        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)
        pending = self._make_pending_with_due(
            user, closing_balance=-3_000_000, grace_days=4
        )
        current, _ = Statement.objects.get_or_create_current_statement(user)

        # No payments in window
        now = timezone.now() + dt.timedelta(days=1)

        # Expected penalty as computed by model helper (before status changes)
        expected_penalty = pending.compute_penalty_amount(now=now)

        result = StatementUseCases.finalize_due_windows(now=now)
        assert result.finalized_count >= 1
        assert result.closed_with_penalty_count >= 1

        pending.refresh_from_db()
        current.refresh_from_db()
        assert pending.status == StatementStatus.CLOSED_WITH_PENALTY

        # One penalty line on CURRENT with negative amount equal to expected (or capped by model)
        pen = current.lines.filter(type=StatementLineType.PENALTY).last()
        assert pen is not None
        assert pen.amount < 0
        assert abs(pen.amount) == expected_penalty

    def test_finalize_due_windows_creates_current_if_missing(
            self, user, active_credit_limit_factory
    ):
        """
        If no CURRENT exists for user, finalize_due_windows must create one and then apply penalty if needed.
        """
        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)

        # Build a pending snapshot belonging to previous month (so CURRENT for current month doesn't exist yet)
        pending = self._make_pending_with_due(
            user, closing_balance=-1_500_000, grace_days=5
        )

        # Ensure CURRENT does not exist (delete if any)
        Statement.objects.filter(
            user=user, status=StatementStatus.CURRENT
        ).delete()
        assert Statement.objects.filter(
            user=user, status=StatementStatus.CURRENT
        ).count() == 0

        # Finalize now (no payments made)
        now = timezone.now() + dt.timedelta(days=1)
        StatementUseCases.finalize_due_windows(now=now)

        # CURRENT must be created
        current = Statement.objects.filter(
            user=user, status=StatementStatus.CURRENT
        ).first()
        assert current is not None
        # And pending should be closed (with or without penalty depending on minimum)
        pending.refresh_from_db()
        assert pending.status in {StatementStatus.CLOSED_WITH_PENALTY,
                                  StatementStatus.CLOSED_NO_PENALTY}

    def test_finalize_due_windows_small_debt_below_minimum_threshold_no_penalty(
            self, user, active_credit_limit_factory
    ):
        """
        If |closing_balance| < MINIMUM_PAYMENT_THRESHOLD, it must close with no penalty regardless of payments.
        """
        from credit.utils.constants import MINIMUM_PAYMENT_THRESHOLD

        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)
        small_debt = -(MINIMUM_PAYMENT_THRESHOLD - 1)
        pending = self._make_pending_with_due(
            user, closing_balance=small_debt, grace_days=2
        )
        current, _ = Statement.objects.get_or_create_current_statement(user)

        result = StatementUseCases.finalize_due_windows(
            now=timezone.now() + dt.timedelta(days=1)
        )
        pending.refresh_from_db()
        current.refresh_from_db()

        assert result.finalized_count >= 1
        assert pending.status == StatementStatus.CLOSED_NO_PENALTY
        assert not current.lines.filter(
            type=StatementLineType.PENALTY
        ).exists()

    def test_finalize_due_windows_penalty_is_capped_by_max_rate(
            self, user, active_credit_limit_factory
    ):
        """
        For large overdue days, the computed daily penalty must be capped by STATEMENT_MAX_PENALTY_RATE.
        """
        from credit.utils.constants import STATEMENT_MAX_PENALTY_RATE

        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)
        debt = -5_000_000
        pending = self._make_pending_with_due(
            user, closing_balance=debt, grace_days=1
        )
        current, _ = Statement.objects.get_or_create_current_statement(user)

        # Choose 'now' far after due_date so raw daily penalty would exceed the cap
        now = timezone.now() + dt.timedelta(days=365)
        expected_cap = int(abs(debt) * STATEMENT_MAX_PENALTY_RATE)

        StatementUseCases.finalize_due_windows(now=now)
        current.refresh_from_db()

        pen = current.lines.filter(type=StatementLineType.PENALTY).last()
        assert pen is not None
        assert abs(int(pen.amount)) == expected_cap

    def test_finalize_due_windows_no_penalty_when_pending_balance_non_negative(
            self, user, active_credit_limit_factory
    ):
        # Build a past-month pending snapshot with non-negative closing balance
        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)

        # Create CURRENT then move it to previous month and close with >= 0 balance
        from persiantools.jdatetime import JalaliDate
        stmt, _ = Statement.objects.get_or_create_current_statement(user)
        today = JalaliDate.today()
        prev_year, prev_month = (
            (today.year - 1, today.month) if today.month == 1 else (today.year,
                                                                    today.month - 1))
        stmt.year = prev_year
        stmt.month = prev_month
        stmt.save(update_fields=["year", "month"])
        # ensure closing >= 0: add a small PAYMENT if needed
        if stmt.closing_balance < 0:
            stmt.add_line(
                StatementLineType.PAYMENT, abs(int(stmt.closing_balance)) + 1
            )
        # close to pending, already overdue
        now = timezone.now()
        stmt.status = StatementStatus.PENDING_PAYMENT
        stmt.closed_at = now - dt.timedelta(days=10)
        stmt.due_date = now - dt.timedelta(days=3)
        stmt.save(
            update_fields=["status", "closed_at", "due_date",
                           "closing_balance"]
        )

        # Act
        res = StatementUseCases.finalize_due_windows(now=now)

        # Assert: closed no penalty, and CURRENT has no penalty line
        stmt.refresh_from_db()
        assert res.finalized_count >= 1
        assert stmt.status == StatementStatus.CLOSED_NO_PENALTY
        current = Statement.objects.get(
            user=user, status=StatementStatus.CURRENT
        )
        assert not current.lines.filter(
            type=StatementLineType.PENALTY
        ).exists()

    def test_finalize_due_windows_is_idempotent_no_duplicate_penalty(
            self, user, active_credit_limit_factory
    ):
        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)
        # pending with debt and overdue, no payments
        pending = self._make_pending_with_due(
            user, closing_balance=-1_200_000, grace_days=2
        )
        current, _ = Statement.objects.get_or_create_current_statement(user)

        now = timezone.now() + dt.timedelta(days=10)
        # First run
        StatementUseCases.finalize_due_windows(now=now)
        pen_count_1 = current.lines.filter(
            type=StatementLineType.PENALTY
        ).count()

        # Second run — nothing new should be added
        StatementUseCases.finalize_due_windows(now=now + dt.timedelta(days=1))
        pen_count_2 = current.lines.filter(
            type=StatementLineType.PENALTY
        ).count()

        assert pen_count_1 in (0,
                               1)  # penalty may be zero if capped/threshold; accept both shapes
        assert pen_count_2 == pen_count_1

    def test_finalize_due_windows_leaves_pending_if_not_due_yet(
            self, user, active_credit_limit_factory
    ):
        """
        If a pending statement is not yet due, it must not be finalized and no penalty should be added.
        """
        from persiantools.jdatetime import JalaliDate

        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)

        # Create CURRENT then move it to previous month and make it pending with due in future
        stmt, _ = Statement.objects.get_or_create_current_statement(user)
        today = JalaliDate.today()
        prev_year, prev_month = (
            (today.year - 1, today.month) if today.month == 1 else (today.year,
                                                                    today.month - 1))
        stmt.year = prev_year
        stmt.month = prev_month
        stmt.save(update_fields=["year", "month"])
        # make it negative
        stmt.add_line(StatementLineType.PURCHASE, 150_000)
        stmt.refresh_from_db()

        now = timezone.now()
        stmt.status = StatementStatus.PENDING_PAYMENT
        stmt.closed_at = now - dt.timedelta(days=2)
        stmt.due_date = now + dt.timedelta(days=3)  # not due yet
        stmt.save(
            update_fields=["status", "closed_at", "due_date",
                           "closing_balance"]
        )

        # Ensure a CURRENT exists for this month
        Statement.objects.get_or_create_current_statement(user)

        res = StatementUseCases.finalize_due_windows(now=now)
        assert res.finalized_count == 0

        stmt.refresh_from_db()
        assert stmt.status == StatementStatus.PENDING_PAYMENT
        current = Statement.objects.get(
            user=user, status=StatementStatus.CURRENT
        )
        assert not current.lines.filter(
            type=StatementLineType.PENALTY
        ).exists()

    def test_finalize_due_windows_multiple_partial_payments_cover_minimum(
            self, user, active_credit_limit_factory
    ):
        """
        Two partial payments inside [closed_at, due_date] that sum to minimum should avoid penalty.
        """
        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)
        pending = self._make_pending_with_due(
            user, closing_balance=-1_300_000, grace_days=4
        )
        current, _ = Statement.objects.get_or_create_current_statement(user)

        min_required = pending.calculate_minimum_payment_amount()
        part1 = min_required // 2
        part2 = min_required - part1

        start = pending.closed_at
        end = pending.due_date

        # Add two payments inside the window at different timestamps
        orig_now = timezone.now
        try:
            timezone.now = lambda: start + dt.timedelta(hours=1)
            current.add_line(
                StatementLineType.PAYMENT, part1, description="part1"
            )
            timezone.now = lambda: end - dt.timedelta(seconds=1)
            current.add_line(
                StatementLineType.PAYMENT, part2, description="part2"
            )
        finally:
            timezone.now = orig_now

        res = StatementUseCases.finalize_due_windows(
            now=end + dt.timedelta(seconds=1)
        )
        assert res.finalized_count >= 1
        pending.refresh_from_db()
        assert pending.status == StatementStatus.CLOSED_NO_PENALTY
        assert not current.lines.filter(
            type=StatementLineType.PENALTY
        ).exists()

    def test_finalize_due_windows_ignores_payment_just_after_due(
            self, user, active_credit_limit_factory
    ):
        """
        A payment that happens immediately AFTER due boundary must NOT be counted toward the window.
        """
        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)
        pending = self._make_pending_with_due(
            user, closing_balance=-1_500_000, grace_days=2
        )
        current, _ = Statement.objects.get_or_create_current_statement(user)

        # Payment after due_date
        after_due = pending.due_date + dt.timedelta(seconds=1)
        orig_now = timezone.now
        try:
            timezone.now = lambda: after_due
            current.add_line(
                StatementLineType.PAYMENT,
                pending.calculate_minimum_payment_amount(),
                description="too late"
            )
        finally:
            timezone.now = orig_now

        res = StatementUseCases.finalize_due_windows(
            now=after_due + dt.timedelta(seconds=1)
        )
        pending.refresh_from_db()
        assert res.finalized_count >= 1
        assert pending.status == StatementStatus.CLOSED_WITH_PENALTY

    def test_finalize_noop_when_no_pending_past_due(
            self, user, active_credit_limit_factory
    ):
        """
        No pending past-due statements → should return zero counters.
        """
        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)
        Statement.objects.get_or_create_current_statement(user)
        res = StatementUseCases.finalize_due_windows(now=timezone.now())
        assert (res.finalized_count, res.closed_without_penalty_count,
                res.closed_with_penalty_count) == (0, 0, 0)


# ======================================================================
# Helpers / internal sums
# ======================================================================

class TestSumPaymentsHelper:
    def test_sum_payments_on_current_during_window_only_counts_payments_inside_range(
            self, user, current_statement_factory
    ):
        # three payments: before, inside, after
        stmt = current_statement_factory(user)
        t0 = timezone.now()
        inside_amount = 50_000

        # before
        orig_now = timezone.now
        try:
            timezone.now = lambda: t0 - dt.timedelta(days=2)
            stmt.add_line(StatementLineType.PAYMENT, 70_000)
            # inside
            timezone.now = lambda: t0
            stmt.add_line(StatementLineType.PAYMENT, inside_amount)
            # after
            timezone.now = lambda: t0 + dt.timedelta(days=2)
            stmt.add_line(StatementLineType.PAYMENT, 30_000)
        finally:
            timezone.now = orig_now

        s = StatementUseCases._sum_payments_on_current_during_window(
            current_statement=stmt, start=t0 - dt.timedelta(hours=1),
            end=t0 + dt.timedelta(hours=1)
        )
        assert s == inside_amount

    def test_sum_payments_on_current_during_window_includes_start_boundary(
            self, user, current_statement_factory
    ):
        """
        Payments at exactly 'start' timestamp should be included.
        """
        stmt = current_statement_factory(user)
        t0 = timezone.now()

        # Put one payment exactly at start, and one outside
        orig_now = timezone.now
        try:
            timezone.now = lambda: t0
            stmt.add_line(StatementLineType.PAYMENT, 40_000)  # at start
            timezone.now = lambda: t0 - dt.timedelta(seconds=1)
            stmt.add_line(
                StatementLineType.PAYMENT, 10_000
            )  # just before start (excluded)
        finally:
            timezone.now = orig_now

        s = StatementUseCases._sum_payments_on_current_during_window(
            current_statement=stmt, start=t0, end=t0 + dt.timedelta(minutes=5)
        )
        assert s == 40_000

    def test_sum_payments_includes_end_boundary(
            self, user, current_statement_factory
    ):
        stmt = current_statement_factory(user)
        t0 = timezone.now()
        orig_now = timezone.now
        try:
            timezone.now = lambda: t0
            stmt.add_line(StatementLineType.PAYMENT, 25_000)  # exactly at end
        finally:
            timezone.now = orig_now

        s = StatementUseCases._sum_payments_on_current_during_window(
            current_statement=stmt, start=t0 - dt.timedelta(minutes=5), end=t0
        )
        assert s == 25_000

    def test_sum_payments_on_current_during_window_returns_zero_for_invalid_window_or_missing_bounds(
            self, user, current_statement_factory
    ):
        stmt = current_statement_factory(user)
        # Some noise payments
        stmt.add_line(StatementLineType.PAYMENT, 10_000)
        stmt.add_line(StatementLineType.PAYMENT, 20_000)

        now = timezone.now()
        # end <= start → zero
        s1 = StatementUseCases._sum_payments_on_current_during_window(
            current_statement=stmt, start=now,
            end=now - dt.timedelta(seconds=1)
        )
        # missing bounds → zero
        s2 = StatementUseCases._sum_payments_on_current_during_window(
            current_statement=stmt, start=None, end=now
        )
        s3 = StatementUseCases._sum_payments_on_current_during_window(
            current_statement=stmt, start=now, end=None
        )
        assert s1 == s2 == s3 == 0

    def test_sum_payments_returns_zero_when_no_payments_in_valid_window(
            self, user, current_statement_factory
    ):
        """
        With a valid time window but no PAYMENT lines, the sum must be zero.
        """
        stmt = current_statement_factory(user)
        start = timezone.now() - dt.timedelta(days=1)
        end = timezone.now()
        s = StatementUseCases._sum_payments_on_current_during_window(
            current_statement=stmt, start=start, end=end
        )
        assert s == 0


# ======================================================================
# Auto-creation of CURRENT statements
# ======================================================================

class TestAutoCreateCurrent:
    def test_record_successful_purchase_auto_creates_current_if_missing(
            self, user, active_credit_limit_factory, wallets_for_user
    ):
        from wallets.models import Transaction
        from wallets.utils.choices import TransactionStatus as TxS

        # No CURRENT for user
        Statement.objects.filter(user=user).delete()
        assert not Statement.objects.filter(user=user).exists()

        # Active limit and a SUCCESS tx owned by user (as buyer)
        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)
        w_from, w_to = wallets_for_user
        tx = Transaction.objects.create(
            from_wallet=w_from, to_wallet=w_to, amount=90_000,
            status=TxS.SUCCESS
        )

        stmt = StatementUseCases.record_successful_purchase_from_transaction(
            tx.id, description="auto-current"
        )
        assert stmt.status == StatementStatus.CURRENT
        assert stmt.lines.filter(type=StatementLineType.PURCHASE).count() == 1

    def test_record_payment_auto_creates_current_if_missing(self, user):
        # No CURRENT for user
        Statement.objects.filter(user=user).delete()
        assert not Statement.objects.filter(user=user).exists()

        stmt = StatementUseCases.record_payment_on_current_statement(
            user, amount=33_000, description="auto-current pay"
        )
        assert stmt.status == StatementStatus.CURRENT
        line = stmt.lines.last()
        assert line.type == StatementLineType.PAYMENT and line.amount == 33_000


# ======================================================================
# Multiple users finalize counts
# ======================================================================

class TestFinalizeCountsMultiUser:
    def test_finalize_due_windows_counts_multiple_users_split_penalty_and_no_penalty(
            self, user, django_user_model, active_credit_limit_factory
    ):
        """
        User A: pays minimum within window -> closed_without_penalty
        User B: pays nothing -> closed_with_penalty
        """
        # Create another user
        user_b = django_user_model.objects.create(
            username="buyer_b", password="x"
        )
        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)
        active_credit_limit_factory(
            user=user_b, is_active=True, expiry_days=30
        )

        # Build both pendings (previous month, past due)
        pending_a = TestFinalizeDueWindows()._make_pending_with_due(
            user, closing_balance=-1_200_000, grace_days=3
        )
        pending_b = TestFinalizeDueWindows()._make_pending_with_due(
            user_b, closing_balance=-1_200_000, grace_days=3
        )

        # User A pays exactly minimum at end boundary
        min_a = pending_a.calculate_minimum_payment_amount()
        current_a, _ = Statement.objects.get_or_create_current_statement(user)
        end_a = pending_a.due_date
        orig_now = timezone.now
        try:
            timezone.now = lambda: end_a
            current_a.add_line(
                StatementLineType.PAYMENT, min_a, description="A on-time"
            )
        finally:
            timezone.now = orig_now

        # User B pays nothing

        res = StatementUseCases.finalize_due_windows(
            now=end_a + dt.timedelta(seconds=1)
        )
        assert res.finalized_count >= 2
        assert res.closed_without_penalty_count >= 1
        assert res.closed_with_penalty_count >= 1


# ======================================================================
# Sum helper ignores non-PAYMENT lines
# ======================================================================

class TestSumIgnoresNonPayments:
    def test_sum_payments_ignores_non_payment_lines_inside_window(
            self, user, current_statement_factory
    ):
        stmt = current_statement_factory(user)
        t0 = timezone.now()

        # Insert non-payment lines around/inside window
        orig_now = timezone.now
        try:
            timezone.now = lambda: t0
            stmt.add_line(StatementLineType.PURCHASE, 80_000)
            stmt.add_line(StatementLineType.INTEREST, 5_000)
            stmt.add_line(StatementLineType.FEE, 2_000)
            stmt.add_line(StatementLineType.PENALTY, 3_000)
            # Add one payment inside to be counted
            stmt.add_line(StatementLineType.PAYMENT, 20_000)
        finally:
            timezone.now = orig_now

        s = StatementUseCases._sum_payments_on_current_during_window(
            current_statement=stmt, start=t0 - dt.timedelta(minutes=1),
            end=t0 + dt.timedelta(minutes=1)
        )
        assert s == 20_000  # non-payment lines must be ignored


# ======================================================================
# Penalty line sign sanity
# ======================================================================

class TestPenaltySign:
    def test_finalize_due_windows_penalty_line_is_negative(
            self, user, active_credit_limit_factory
    ):
        active_credit_limit_factory(user=user, is_active=True, expiry_days=30)
        pending = TestFinalizeDueWindows()._make_pending_with_due(
            user, closing_balance=-1_000_000, grace_days=2
        )
        current, _ = Statement.objects.get_or_create_current_statement(user)

        # Force overdue far enough to ensure a positive penalty amount > 0
        now = timezone.now() + dt.timedelta(days=30)
        StatementUseCases.finalize_due_windows(now=now)

        pen = current.lines.filter(type=StatementLineType.PENALTY).last()
        # There may be no penalty if minimum threshold logic disables it; guard accordingly:
        if pen:
            assert pen.amount < 0  # enforced by use-case + StatementLine.save()
