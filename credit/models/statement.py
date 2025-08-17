# credit/models/statement.py

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db import IntegrityError
from django.db import transaction
from django.db.models import Sum, Case, When, Value, IntegerField, F

from lib.erp_base.models import BaseModel
from wallets.utils.choices import TransactionStatus
from credit.models.statement_line import StatementLine
from credit.utils.reference import generate_statement_reference
from persiantools.jdatetime import JalaliDate
from credit import settings as credit_settings
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
                            abs(statement.closing_balance)
                            * credit_settings.MONTHLY_INTEREST_RATE
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
            status="current",
            reference_code=generate_statement_reference(),
        )


class Statement(BaseModel):
    STATUS_CHOICES = [
        ("current", _("جاری")),
        ("pending_payment", _("در انتظار پرداخت")),
        ("closed_no_penalty", _("بسته شده - بدون جریمه")),
        ("closed_with_penalty", _("بسته شده - با جریمه")),
        ("overdue", _("سررسید گذشته")),
    ]

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
        max_length=20, choices=STATUS_CHOICES, default="current", verbose_name=_("وضعیت")
    )

    opening_balance = models.BigIntegerField(default=0, verbose_name=_("مانده اول دوره"))

    closing_balance = models.BigIntegerField(
        default=0, verbose_name=_("مانده پایان دوره")
    )

    total_debit = models.BigIntegerField(default=0, verbose_name=_("مجموع بدهکار"))

    total_credit = models.BigIntegerField(default=0, verbose_name=_("مجموع بستانکار"))

    due_date = models.DateTimeField(null=True, blank=True, verbose_name=_("تاریخ سررسید"))

    paid_at = models.DateTimeField(null=True, blank=True, verbose_name=_("زمان پرداخت"))

    # --- Closing and carryover tracking ---
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("زمان بستن"))

    carried_over = models.BooleanField(
        default=False, verbose_name=_("انتقال یافته به دوره بعد")
    )

    objects = StatementManager()

    class Meta:
        verbose_name = _("صورتحساب اعتباری")
        verbose_name_plural = _("صورتحساب‌های اعتباری")
        ordering = ["-year", "-month"]
        unique_together = ["user", "year", "month"]
        indexes = [
            models.Index(fields=["user", "status"], name="st_user_status_idx"),
            models.Index(fields=["due_date"], name="st_due_idx"),
        ]

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

    def close_statement(self):
        """Close current statement and prepare for payment"""

        # Only close if currently open
        if self.status != "current":
            return
        self.update_balances()
        now = timezone.now()
        self.status = "pending_payment"
        # due date = close time + configured due days (not grace)
        due_days = int(credit_settings.STATEMENT_DUE_DAYS)
        self.closed_at = now
        self.due_date = now + timedelta(days=due_days)
        self.save(update_fields=["status", "due_date", "closing_balance", "closed_at"])

    def calculate_penalty(self, penalty_rate=None, max_penalty_rate=None):
        """
        Calculate penalty amount based on overdue days

        Args:
            penalty_rate: Daily penalty rate (uses settings.CREDIT_STATEMENT_PENALTY_RATE if None)
            max_penalty_rate: Maximum penalty cap (uses settings.CREDIT_STATEMENT_MAX_PENALTY_RATE if None)

        Returns:
            int: Calculated penalty amount
        """
        from credit import settings as credit_settings

        penalty_rate = penalty_rate or credit_settings.STATEMENT_PENALTY_RATE
        max_penalty_rate = max_penalty_rate or credit_settings.STATEMENT_MAX_PENALTY_RATE
        # Only apply penalty on pending or overdue statements
        if self.status not in {"pending_payment", "overdue"}:
            return 0
        # Only apply penalty on pending or overdue statements
        if self.status not in {"pending_payment", "overdue"}:
            return 0

        if not self.due_date or timezone.now() <= self.due_date:
            return 0

        overdue_days = (timezone.now() - self.due_date).days
        if overdue_days <= 0:
            return 0

        # Penalty only when there is debt (negative closing balance)
        if self.closing_balance >= 0:
            return 0
        base_amount = -int(self.closing_balance)
        penalty_amount = int(base_amount * penalty_rate * overdue_days)
        max_penalty = int(base_amount * max_penalty_rate)
        
        return min(penalty_amount, max_penalty)

    def add_line(self, type_, amount, transaction=None, description=""):
        """Add a line to the statement.
        Only allowed if statement status is 'current'.
        Raises:
            ValueError: If statement status is not 'current'.
        """
        if self.status != "current":
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
        # Consume credit limit and add purchase line

        cl = CreditLimit.objects.get_user_credit_limit(self.user)
        if not cl:
            raise ValueError("حد اعتباری فعال یافت نشد")
        purchase_amount = abs(int(transaction.amount))
        cl.use_credit(purchase_amount)
        self.add_line(
            "purchase", -purchase_amount, transaction=transaction, description="خرید"
        )

    def apply_payment(self, amount, transaction=None):
        """Add a payment line and update credit limit"""
        pay_amount = abs(int(amount))
        self.add_line(
            "payment", pay_amount, transaction=transaction, description="پرداخت"
        )
        # Sync with CreditLimit.release_credit(amount)
        try:
            from credit.models.credit_limit import CreditLimit

            cl = CreditLimit.objects.get_user_credit_limit(self.user)
            if cl:
                cl.release_credit(pay_amount)
        except Exception:
            # Do not block on credit limit sync
            pass
        # Note: Payment processing logic moved to process_pending_payments command
        # This method just records the payment

    def apply_fee(self, amount, description="کارمزد"):
        self.add_line("fee", -abs(amount), description=description)

    def apply_penalty(self, amount, description="جریمه"):
        self.add_line("penalty", -abs(amount), description=description)

    def calculate_and_apply_penalty(self, penalty_rate=None, max_penalty_rate=None):
        """Calculate and apply penalty as a statement line if overdue and not already present."""
        from credit import settings as credit_settings

        penalty_rate = penalty_rate or credit_settings.STATEMENT_PENALTY_RATE
        max_penalty_rate = max_penalty_rate or credit_settings.STATEMENT_MAX_PENALTY_RATE

        # If past due mark as overdue prior to calculation
        if (
            self.due_date
            and timezone.now() > self.due_date
            and self.status == "pending_payment"
        ):
            self.status = "overdue"
            self.save(update_fields=["status"])

        penalty = self.calculate_penalty(penalty_rate, max_penalty_rate)
        if penalty > 0 and not self.lines.filter(type="penalty").exists():
            self.apply_penalty(penalty)
        return penalty

    # --- Due days helpers ---
    def get_due_days(self) -> int:
        """Due days for this user: per-user override via CreditLimit or default settings."""
        from credit.models.credit_limit import CreditLimit
        from credit import settings as credit_settings

        cl = CreditLimit.objects.get_user_credit_limit(self.user)
        return (
            cl.get_due_days()
            if cl
            else int(credit_settings.STATEMENT_DUE_DAYS)
        )

    @property
    def due_ends_at(self):
        if not self.due_date:
            return None
        return self.due_date + timedelta(days=self.get_due_days())

    def is_within_due(self, now=None) -> bool:
        """Return True if now is within the due window after statement closure (before or at due date).
        There is no grace period; only the due date matters for timely payment to avoid penalty. After the due date, penalty and/or interest may be applied.
        """
        if not self.due_date:
            return False
        now = now or timezone.now()
        return now <= self.due_date

    def calculate_minimum_payment_amount(self):
        """Calculate the minimum payment amount based on closing balance"""
        from credit import settings as credit_settings

        # Only calculate for pending payment statements with debt
        if self.status != "pending_payment" or self.closing_balance >= 0:
            return 0

        debt_amount = abs(self.closing_balance)

        # If debt is below threshold, no minimum payment required
        if debt_amount < credit_settings.MINIMUM_PAYMENT_THRESHOLD:
            return 0

        # Calculate minimum payment as percentage of debt
        min_payment = debt_amount * credit_settings.MINIMUM_PAYMENT_PERCENTAGE
        return int(min_payment)

    def process_payment_during_grace_period(self, payment_amount):
        """Process payment during grace period and determine statement outcome"""
        from credit import settings as credit_settings

        if self.status != "pending_payment":
            raise ValueError("Can only process payment for pending payment statements")

        min_required = self.calculate_minimum_payment_amount()

        # Check if payment meets minimum requirement or debt is below threshold
        debt_amount = abs(self.closing_balance) if self.closing_balance < 0 else 0

        if debt_amount < credit_settings.MINIMUM_PAYMENT_THRESHOLD:
            # Debt below threshold - no penalty regardless of payment amount
            self.status = "closed_no_penalty"
            self.closed_at = timezone.now()
            self.save(update_fields=["status", "closed_at"])
            return "closed_no_penalty"

        if payment_amount >= min_required:
            # Payment meets minimum requirement
            self.status = "closed_no_penalty"
            self.closed_at = timezone.now()
            self.save(update_fields=["status", "closed_at"])
            return "closed_no_penalty"
        else:
            # Payment doesn't meet minimum requirement
            self.status = "closed_with_penalty"
            self.closed_at = timezone.now()
            self.save(update_fields=["status", "closed_at"])
            return "closed_with_penalty"

    def apply_penalty_to_current_statement(self, penalty_amount=None):
        """Apply penalty to the user's current statement"""
        from credit.models.statement import Statement

        # Get user's current statement
        current_statement = Statement.objects.get_current_statement(self.user)
        if not current_statement:
            raise ValueError(
                "Cannot apply penalty: user does not have any statement with 'current' status."
            )

        if penalty_amount is None:
            # Use constant penalty for now (100,000 Rials)
            penalty_amount = 100000

        # Add penalty line to current statement
        current_statement.add_line(
            type="penalty",
            amount=-penalty_amount,
            description=f"جریمه عدم پرداخت دوره {self.year}/{self.month:02d}",
        )

        return penalty_amount
