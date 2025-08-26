# credit/models/statement.py

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db import IntegrityError
from django.db import transaction
from django.db.models import Sum, Case, When, Value, IntegerField, F
from credit.utils.choices import StatementStatus

from lib.erp_base.models import BaseModel
from wallets.utils.choices import TransactionStatus
from credit.models.statement_line import StatementLine
from credit.utils.reference import generate_statement_reference
from persiantools.jdatetime import JalaliDate
from credit.utils.constants import (
    MONTHLY_INTEREST_RATE,
    STATEMENT_GRACE_DAYS,
    STATEMENT_PENALTY_RATE,
    STATEMENT_MAX_PENALTY_RATE,
    MINIMUM_PAYMENT_PERCENTAGE,
    MINIMUM_PAYMENT_THRESHOLD,
)
from credit.models.credit_limit import CreditLimit


class StatementManager(models.Manager):
    def get_current_statement(self, user):
        """Get the user's current (active) statement"""
        return self.filter(user=user, status="current").first()

    def get_or_create_current_statement(self, user, starting_balance=0):
        """Get or create current statement for user, with explicit starting balance if creating new"""
        current = self.get_current_statement(user)
        if current:
            return current, False

        # Create new current statement
        jtoday = JalaliDate.today()

        statement = self.create(
            user=user,
            year=jtoday.year,
            month=jtoday.month,
            status="current",
            reference_code=generate_statement_reference(),
            opening_balance=starting_balance,
        )
        return statement, True

    def close_monthly_statements(self):
        """Close all current statements from previous months and create new ones with new workflow"""

        today = JalaliDate.today()

        with transaction.atomic():
            # Find all current statements from previous months
            current_statements = self.filter(status="current")

            for statement in current_statements:
                # Check if this statement is from a previous month
                if statement.year < today.year or (
                    statement.year == today.year and statement.month < today.month
                ):
                    # Close previous statement and set to pending_payment
                    statement.close_statement()

                    # Create new current month statement
                    new_statement, created = self.get_or_create(
                        user=statement.user,
                        year=today.year,
                        month=today.month,
                        defaults={
                            "status": "current",
                            "reference_code": generate_statement_reference(),
                            "opening_balance": statement.closing_balance,  # Starting balance equals previous closing
                        },
                    )

                    # Ensure new statement has correct opening balance
                    if created:
                        new_statement.opening_balance = statement.closing_balance
                        new_statement.save(update_fields=["opening_balance"])

                    # Add interest as first transaction if there's debt
                    if statement.closing_balance < 0:  # Negative balance means debt
                        interest_amount = (
                            abs(statement.closing_balance) * MONTHLY_INTEREST_RATE
                        )
                        StatementLine.objects.create(
                            statement=new_statement,
                            type="interest",
                            amount=-int(interest_amount),  # Negative as it's a charge
                            description=(
                                f"سود بدهی دوره {statement.year}/{statement.month:02d}"
                            ),
                        )
                        new_statement.update_balances()

    def create_initial_statement(self, user):
        """Create initial statement when credit limit is assigned"""
        today = JalaliDate.today()
        return self.create(
            user=user,
            year=today.year,
            month=today.month,
            status=StatementStatus.CURRENT,
            reference_code=generate_statement_reference(),
        )


class Statement(BaseModel):
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="statements",
        verbose_name=_("کاربر"),
    )

    year = models.PositiveIntegerField(verbose_name=_("سال شمسی"))

    month = models.PositiveIntegerField(verbose_name=_("ماه شمسی"))

    reference_code = models.CharField(
        max_length=20, unique=True, null=True, blank=True, verbose_name=_("کد پیگیری")
    )

    status = models.CharField(
        max_length=20,
        choices=StatementStatus.choices,
        default=StatementStatus.CURRENT,
        verbose_name=_("وضعیت"),
    )

    opening_balance = models.BigIntegerField(default=0, verbose_name=_("مانده اول دوره"))

    closing_balance = models.BigIntegerField(
        default=0, verbose_name=_("مانده پایان دوره")
    )

    total_debit = models.BigIntegerField(default=0, verbose_name=_("مجموع بدهکار"))

    total_credit = models.BigIntegerField(default=0, verbose_name=_("مجموع بستانکار"))

    grace_date = models.DateTimeField(
        null=True, blank=True, verbose_name=_("تاریخ سررسید")
    )

    paid_at = models.DateTimeField(null=True, blank=True, verbose_name=_("زمان پرداخت"))

    # --- Closing and carryover tracking ---
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("زمان بستن"))

    objects = StatementManager()

    def __str__(self):
        return f"{self.user} - {self.year}/{self.month:02d} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.reference_code:
            # Retry a few times to avoid rare collisions
            for _ in range(5):
                self.reference_code = generate_statement_reference()
                try:
                    return super().save(*args, **kwargs)
                except IntegrityError:
                    self.reference_code = None
            # Fall-through to raise if still colliding
        return super().save(*args, **kwargs)

    @property
    def current_balance(self):
        """Calculate current balance based on statement lines"""
        # Purchases, fees, penalties are negative; payments are positive
        return self.closing_balance

    def update_balances(self):
        """Update statement balances based on statement lines atomically"""

        with transaction.atomic():
            statement = Statement.objects.select_for_update().get(pk=self.pk)

            # Calculate totals atomically using database aggregation
            totals = statement.lines.aggregate(
                total_debit=Sum(
                    Case(
                        When(amount__lt=0, then=-F("amount")),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
                total_credit=Sum(
                    Case(
                        When(amount__gt=0, then="amount"),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
            )

            total_debit = totals["total_debit"] or 0
            total_credit = totals["total_credit"] or 0
            closing_balance = statement.opening_balance + total_credit - total_debit

            Statement.objects.filter(pk=self.pk).update(
                total_debit=total_debit,
                total_credit=total_credit,
                closing_balance=closing_balance,
            )

            # Refresh from db to get updated values
            self.refresh_from_db()
            
            # Sync used_limit with current statement's closing balance if this is the current statement
            if self.status == StatementStatus.CURRENT:
                self._sync_credit_limit_used_amount()

    def close_statement(self):
        """Close current statement and prepare for payment"""

        # Only close if currently open
        if self.status != "current":
            return
        self.update_balances()
        now = timezone.now()
        self.status = "pending_payment"
        
        # Use credit limit's grace period or default
        grace_days = self.get_grace_days()
        self.closed_at = now
        self.grace_date = now + timedelta(days=grace_days)
        self.save(update_fields=["status", "grace_date", "closing_balance", "closed_at"])
        
        # Sync credit limit after closing statement
        self._sync_credit_limit_used_amount()

    def calculate_penalty(self, penalty_rate=None):
        """
        Calculate penalty amount based on overgrace days

        Args:
            penalty_rate: Daily penalty rate (uses settings.CREDIT_STATEMENT_PENALTY_RATE if None)
            max_penalty_rate: Maximum penalty cap (uses settings.CREDIT_STATEMENT_MAX_PENALTY_RATE if None)

        Returns:
            int: Calculated penalty amount
        """
        penalty_rate = penalty_rate or STATEMENT_PENALTY_RATE
        max_penalty_rate = max_penalty_rate or STATEMENT_MAX_PENALTY_RATE
        # Only apply penalty on pending statements
        if self.status != StatementStatus.PENDING_PAYMENT:
            return 0

        # Penalty only when there is debt (negative closing balance)
        if self.closing_balance >= 0:
            return 0
        if self.closing_balance >= MINIMUM_PAYMENT_THRESHOLD:
            return 0
        base_amount = -int(self.closing_balance)
        penalty_amount = int(base_amount * penalty_rate)

        return penalty_amount

    @property
    def is_in_grace_period(self):
        """Checks if the statement is currently within its grace period."""
        if not self.grace_date:
            return False
        return timezone.now().date() <= self.grace_date

    def add_line(self, type_, amount, transaction=None, description=""):
        """Add a line to the statement.
        Only allowed if statement status is 'current'.
        Raises:
            ValueError: If statement status is not 'current'.
        """
        if self.status != StatementStatus.CURRENT:
            raise ValueError("Cannot add line to statement unless status is 'current'")

        # Sign expectation for each line type
        sign_expectation = {
            "purchase": -1,
            "payment": 1,
            "fee": -1,
            "penalty": -1,
            "interest": -1,
            "repayment": 1,
        }
        if type_ in sign_expectation:
            exp = sign_expectation[type_]
            if exp == -1 and amount > 0:
                amount = -abs(int(amount))
            elif exp == 1 and amount < 0:
                amount = abs(int(amount))
        StatementLine.objects.create(
            statement=self,
            type=type_,
            amount=amount,
            transaction=transaction,
            description=description,
        )

    def add_transaction(self, transaction):
        """Add purchase line to statement from a transaction"""
        if self.status != "current":
            raise ValueError("Cannot add transaction to non-current statement")
        # Validate successful transaction and user ownership
        if (
            hasattr(transaction, "status")
            and transaction.status != TransactionStatus.SUCCESS
        ):
            raise ValueError("تراکنش نامعتبر یا ناموفق است")
        if not (
            transaction.from_wallet.user_id == self.user_id
            or transaction.to_wallet.user_id == self.user_id
        ):
            raise ValueError("تراکنش متعلق به کاربر نیست")
        
        # Validate credit limit comprehensively
        cl = CreditLimit.objects.get_user_credit_limit(self.user)
        if not cl:
            raise ValueError("حد اعتباری فعال یافت نشد")
        
        # Validate credit limit status
        if cl.status != "active":
            raise ValueError("حد اعتباری غیرفعال است")
        
        # Validate credit limit expiry
        if cl.expiry_date <= timezone.localdate():
            raise ValueError("حد اعتباری منقضی شده است")
        
        purchase_amount = abs(int(transaction.amount))
        if purchase_amount > cl.available_limit:
            raise ValueError("مبلغ بیشتر از اعتبار موجود است")
        
        # Add purchase line - used_limit will be synced automatically via update_balances()
        self.add_line(
            "purchase", -purchase_amount, transaction=transaction, description="خرید"
        )

    def apply_payment(self, amount, transaction=None):
        """Add a payment line and update credit limit"""
        pay_amount = abs(int(amount))
        
        # Validate credit limit exists (for consistency, though payments should always be allowed)
        cl = CreditLimit.objects.get_user_credit_limit(self.user)
        if not cl:
            # Log warning but don't block payment
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Payment applied for user {self.user_id} without active credit limit")
        
        self.add_line(
            "payment", pay_amount, transaction=transaction, description="پرداخت"
        )
        # Note: We no longer use cl.release_credit() as used_limit is now synced automatically
        # through _sync_credit_limit_used_amount() when statement balances are updated
        # Note: Payment processing logic moved to process_pending_payments command
        # This method just records the payment

    def apply_fee(self, amount, description="کارمزد"):
        self.add_line("fee", -abs(amount), description=description)

    def apply_penalty(self, amount, description="جریمه"):
        self.add_line("penalty", -abs(amount), description=description)

    def calculate_and_apply_penalty(self, penalty_rate=None):
        """Calculate and apply penalty as a statement line if overgrace and not already present."""
        penalty_rate = penalty_rate or STATEMENT_PENALTY_RATE

        # If past due mark as overgrace prior to calculation
        if (
            self.grace_date
            and timezone.now() > self.grace_date
            and self.status == "pending_payment"
        ):
            self.status = "overgrace"
            self.save(update_fields=["status"])

        penalty = self.calculate_penalty(penalty_rate)
        if penalty > 0 and not self.lines.filter(type="penalty").exists():
            self.apply_penalty(penalty)
        return penalty

    # --- Grace days helpers ---
    def get_grace_days(self) -> int:
        """Grace days for this user: per-user override via CreditLimit or default settings."""

        cl = CreditLimit.objects.get_user_credit_limit(self.user)
        return cl.get_grace_days() if cl else int(STATEMENT_GRACE_DAYS)

    @property
    def grace_ends_at(self):
        """Return the grace period end datetime for this statement."""
        return self.grace_date

    def calculate_minimum_payment_amount(self):
        """Calculate the minimum payment amount based on closing balance"""
        # Only calculate for pending payment statements with debt
        if self.status != "pending_payment" or self.closing_balance >= 0:
            return 0

        debt_amount = abs(self.closing_balance)

        # If debt is below threshold, no minimum payment required
        if debt_amount < MINIMUM_PAYMENT_THRESHOLD:
            return 0

        # Calculate minimum payment as percentage of debt
        min_payment = debt_amount * MINIMUM_PAYMENT_PERCENTAGE
        return int(min_payment)

    def process_payment_during_grace_period(self, payment_amount):
        """
        Process payment during grace period and determine statement outcome.
        Returns:
            str: 'closed_no_penalty' if payment/debt is sufficient, else 'closed_with_penalty'.
        """
        if self.status != "pending_payment":
            raise ValueError("Can only process payment for pending payment statements")

        min_required = self.calculate_minimum_payment_amount()
        debt_amount = abs(self.closing_balance) if self.closing_balance < 0 else 0

        if debt_amount < MINIMUM_PAYMENT_THRESHOLD:
            # Debt below threshold - no penalty regardless of payment amount
            self.status = "closed_no_penalty"
            self.closed_at = timezone.now()
            self.save(update_fields=["status", "closed_at"])
            self._sync_credit_limit_used_amount()
            return "closed_no_penalty"

        if payment_amount >= min_required:
            self.status = "closed_no_penalty"
            self.closed_at = timezone.now()
            self.save(update_fields=["status", "closed_at"])
            self._sync_credit_limit_used_amount()
            return "closed_no_penalty"
        else:
            self.status = "closed_with_penalty"
            self.closed_at = timezone.now()
            self.save(update_fields=["status", "closed_at"])
            self._sync_credit_limit_used_amount()
            return "closed_with_penalty"

    def apply_penalty_to_current_statement(self, penalty_amount=None):
        """Apply penalty to the user's current statement"""

        # Get user's current statement
        current_statement = Statement.objects.get_current_statement(self.user)
        if not current_statement:
            raise ValueError(
                (
                    "Cannot apply penalty: user does not have any statement with "
                    "'current' status."
                )
            )

        if penalty_amount is None:
            # Use constant penalty for now (100,000 Rials)
            penalty_amount = self.calculate_penalty()

        # Add penalty line to current statement
        current_statement.add_line(
            type="penalty",
            amount=-penalty_amount,
            description=f"جریمه عدم پرداخت دوره {self.year}/{self.month:02d}",
        )

        return penalty_amount

    def _sync_credit_limit_used_amount(self):
        """
        Sync CreditLimit.used_limit with the current statement's debt amount.
        This ensures used_limit accurately reflects the actual outstanding debt.
        """
        try:
            credit_limit = CreditLimit.objects.get_user_credit_limit(self.user)
            if not credit_limit:
                return
            
            # Calculate total debt across all statements for this user
            # Current statement debt (negative closing_balance means debt)
            current_debt = abs(min(0, self.closing_balance))
            
            # Add debt from any pending payment statements
            pending_statements = Statement.objects.filter(
                user=self.user,
                status__in=[StatementStatus.PENDING_PAYMENT, StatementStatus.OVERGRACE]
            )
            
            pending_debt = 0
            for stmt in pending_statements:
                if stmt.closing_balance < 0:
                    pending_debt += abs(stmt.closing_balance)
            
            # Total used limit should be current debt + pending debt
            total_used_limit = current_debt + pending_debt
            
            # Update credit limit atomically
            with transaction.atomic():
                CreditLimit.objects.filter(pk=credit_limit.pk).update(
                    used_limit=total_used_limit
                )
                
        except Exception as e:
            # Log the error but don't break the statement update process
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to sync credit limit used_limit: {e}")

    class Meta:
        verbose_name = _("صورتحساب اعتباری")
        verbose_name_plural = _("صورتحساب‌های اعتباری")
        ordering = ["-year", "-month"]
        unique_together = ["user", "year", "month"]
        indexes = [
            models.Index(fields=["user", "status"], name="st_user_status_idx"),
            models.Index(fields=["grace_date"], name="st_grace_idx"),
        ]
