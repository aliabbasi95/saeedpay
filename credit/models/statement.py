# credit/models/statement.py

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, models, transaction
from django.db.models import Sum, Case, When, Value, IntegerField, F
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from persiantools.jdatetime import JalaliDate

from credit.utils.choices import StatementStatus, StatementLineType
from credit.utils.constants import (
    MONTHLY_INTEREST_RATE,
    MINIMUM_PAYMENT_PERCENTAGE,
    MINIMUM_PAYMENT_THRESHOLD, STATEMENT_PENALTY_RATE,
    STATEMENT_MAX_PENALTY_RATE,
)
from utils.reference import generate_reference_code
from lib.erp_base.models import BaseModel
from lib.erp_base.utils.choices import JalaliYearChoices, JalaliMonthChoices


class StatementManager(models.Manager):
    def get_current_statement(self, user):
        return self.filter(user=user, status=StatementStatus.CURRENT).first()

    def get_or_create_current_statement(self, user, starting_balance=0):
        current_statement = self.get_current_statement(user)
        if current_statement:
            return current_statement, False

        jalali_today = JalaliDate.today()

        statement = self.create(
            user=user,
            year=jalali_today.year,
            month=jalali_today.month,
            status=StatementStatus.CURRENT,
            opening_balance=starting_balance,
        )
        return statement, True

    @transaction.atomic
    def close_monthly_statements(self):
        """
        Close any 'current' statements belonging to past Persian months,
        then create a new current statement per user and carry over balances.
        Adds monthly interest on carried-over negative balances.
        """
        jalali_today = JalaliDate.today()
        closed_count = 0
        created_count = 0
        interest_lines = 0

        current_statements = self.filter(status=StatementStatus.CURRENT)
        for statement in current_statements:
            if statement.year < jalali_today.year or (
                    statement.year == jalali_today.year and statement.month < jalali_today.month
            ):
                statement.close_statement()
                closed_count += 1

                new_statement, created = self.get_or_create(
                    user=statement.user,
                    year=jalali_today.year,
                    month=jalali_today.month,
                    defaults={
                        "status": StatementStatus.CURRENT,
                        "opening_balance": statement.closing_balance,
                    },
                )

                if created:
                    created_count += 1
                else:
                    new_statement.opening_balance = statement.closing_balance
                    new_statement.save(update_fields=["opening_balance"])

                if statement.closing_balance < 0:
                    interest_amount = int(
                        abs(statement.closing_balance) * MONTHLY_INTEREST_RATE
                    )
                    new_statement.add_line(
                        type_=StatementLineType.INTEREST,
                        amount=-interest_amount,
                        description=f"Monthly interest on {statement.year}/{statement.month:02d}",
                    )
                    interest_lines += 1
        return {
            "statements_closed": closed_count,
            "statements_created": created_count,
            "interest_lines_added": interest_lines,
        }


class Statement(BaseModel):
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="statements",
        verbose_name=_("کاربر"),
    )
    year = models.SmallIntegerField(
        choices=JalaliYearChoices.choices(1404),
        verbose_name=_("سال")
    )
    month = models.SmallIntegerField(
        choices=JalaliMonthChoices.choices,
        verbose_name=_("ماه")
    )
    reference_code = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_("کد پیگیری")
    )

    status = models.CharField(
        max_length=20,
        choices=StatementStatus.choices,
        default=StatementStatus.CURRENT,
        verbose_name=_("وضعیت"),
    )

    opening_balance = models.BigIntegerField(
        default=0,
        verbose_name=_("مانده اول دوره")
    )

    closing_balance = models.BigIntegerField(
        default=0,
        verbose_name=_("مانده پایان دوره")
    )

    total_debit = models.BigIntegerField(
        default=0,
        verbose_name=_("مجموع بدهکار")
    )

    total_credit = models.BigIntegerField(
        default=0,
        verbose_name=_("مجموع بستانکار")
    )
    due_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("تاریخ سررسید")
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("زمان پرداخت")
    )

    # --- Closing and carryover tracking ---
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("زمان بستن")
    )

    objects = StatementManager()

    # ---------- Properties ----------

    @property
    def balance(self) -> int:
        return int(self.closing_balance)

    # ---------- Core mechanics ----------

    @transaction.atomic
    def update_balances(self):
        """
        Recompute totals and closing balance from lines.
        Debit lines are stored negative, but we aggregate them as positive numbers in total_debit.
        """
        locked = Statement.objects.select_for_update().get(pk=self.pk)
        totals = locked.lines.aggregate(
            total_debit=Sum(
                Case(
                    When(amount__lt=0, then=-F("amount")), default=Value(0),
                    output_field=IntegerField()
                    )
                ),
            total_credit=Sum(
                Case(
                    When(amount__gt=0, then="amount"), default=Value(0),
                    output_field=IntegerField()
                    )
                ),
        )
        total_debit = int(totals["total_debit"] or 0)
        total_credit = int(totals["total_credit"] or 0)
        closing_balance = int(
            locked.opening_balance
            ) + total_credit - total_debit

        Statement.objects.filter(pk=self.pk).update(
            total_debit=total_debit, total_credit=total_credit,
            closing_balance=closing_balance
        )
        self.refresh_from_db()

    @transaction.atomic
    def close_statement(self):
        """
        Close a CURRENT statement and move it to PENDING_PAYMENT.
        Sets due_date based on user's active CreditLimit.grace_days.
        """
        if self.status != StatementStatus.CURRENT:
            return

        self.update_balances()

        from credit.models.credit_limit import CreditLimit
        credit_limit = CreditLimit.objects.get_user_credit_limit(self.user)
        grace_days = credit_limit.grace_days if credit_limit else 0

        now = timezone.now()
        self.status = StatementStatus.PENDING_PAYMENT
        self.closed_at = now
        self.due_date = now + timedelta(days=int(grace_days))
        self.save(
            update_fields=["status", "closed_at", "due_date",
                           "closing_balance"]
        )

    def add_line(
            self, type_: str, amount: int, transaction=None,
            description: str = ""
    ):
        """
        Append a line to this statement. Validations are enforced by the caller helpers.
        Negative amounts = charges (purchase/fee/penalty/interest).
        Positive amounts = payments/repayments.
        """
        from credit.models.statement_line import StatementLine

        signed_amount = int(amount)
        if type_ in {StatementLineType.PURCHASE, StatementLineType.FEE,
                     StatementLineType.PENALTY,
                     StatementLineType.INTEREST} and signed_amount > 0:
            signed_amount = -abs(signed_amount)
        elif type_ in {StatementLineType.PAYMENT} and signed_amount < 0:
            signed_amount = abs(signed_amount)

        StatementLine.objects.create(
            statement=self,
            type=type_,
            amount=signed_amount,
            transaction=transaction,
            description=description,
        )

    def add_purchase(self, transaction, description: str = "Purchase"):
        """Add a purchase to CURRENT statement after validating ownership and credit availability."""
        from wallets.utils.choices import TransactionStatus
        from credit.models.credit_limit import CreditLimit

        if self.status != StatementStatus.CURRENT:
            raise ValueError(
                "Purchases can only be added to the current statement."
            )

        if getattr(transaction, "status", None) != TransactionStatus.SUCCESS:
            raise ValueError("Invalid or unsuccessful transaction.")

        if transaction.from_wallet.user_id != self.user_id and transaction.to_wallet.user_id != self.user_id:
            raise ValueError("Transaction does not belong to this user.")

        credit_limit = CreditLimit.objects.get_user_credit_limit(self.user)
        if not credit_limit or not credit_limit.is_active or credit_limit.expiry_date <= timezone.localdate():
            raise ValueError("No active credit limit found.")

        amount = abs(int(transaction.amount))
        if amount > credit_limit.available_limit:
            raise ValueError("Insufficient available credit.")

        self.add_line(
            StatementLineType.PURCHASE, amount, transaction=transaction,
            description=description
        )

    def add_payment(
            self, amount: int, transaction=None, description: str = "Payment"
    ):
        """
        Add a payment to a non-current statement (pending or overdue).
        This reduces the outstanding debt of that closed cycle.
        """
        if self.status not in {StatementStatus.PENDING_PAYMENT,
                               StatementStatus.OVERDUE}:
            raise ValueError(
                "Payments can only be applied to pending or overdue statements."
            )

        pay_amount = abs(int(amount))
        if pay_amount <= 0:
            raise ValueError("Amount must be greater than zero.")

        self.add_line(
            StatementLineType.PAYMENT, pay_amount, transaction=transaction,
            description=description
        )

    # ---------- Due / Minimum payment / Penalty ----------

    def is_within_due(self, now=None) -> bool:
        """True if now is on/before the due_date."""
        if not self.due_date:
            return False
        now = now or timezone.now()
        return now <= self.due_date

    def calculate_minimum_payment_amount(self) -> int:
        """
        Minimum payment for this closed cycle (applies only to pending with negative closing balance).
        """
        if self.status != StatementStatus.PENDING_PAYMENT or self.closing_balance >= 0:
            return 0

        debt = abs(int(self.closing_balance))
        if debt < MINIMUM_PAYMENT_THRESHOLD:
            return 0

        return int(debt * MINIMUM_PAYMENT_PERCENTAGE)

    def determine_due_outcome(self, total_payments_during_due: int) -> str:
        """
        Decide outcome after the due window:
        returns 'closed_no_penalty' or 'closed_with_penalty'.
        """
        if self.status != StatementStatus.PENDING_PAYMENT:
            raise ValueError(
                "Due outcome can be determined only for pending statements."
            )

        min_required = self.calculate_minimum_payment_amount()
        debt = abs(
            int(self.closing_balance)
        ) if self.closing_balance < 0 else 0

        if debt < MINIMUM_PAYMENT_THRESHOLD:
            self.status = StatementStatus.CLOSED_NO_PENALTY
        elif total_payments_during_due >= min_required:
            self.status = StatementStatus.CLOSED_NO_PENALTY
        else:
            self.status = StatementStatus.CLOSED_WITH_PENALTY

        self.closed_at = timezone.now()
        self.save(update_fields=["status", "closed_at"])
        return self.status

    def compute_penalty_amount(self, now=None) -> int:
        """
        Daily penalty on overdue amount capped by STATEMENT_MAX_PENALTY_RATE of base debt.
        Returns total penalty to-date (idempotent consumer should apply delta).
        """
        if self.status not in {StatementStatus.PENDING_PAYMENT,
                               StatementStatus.OVERDUE}:
            return 0
        if self.closing_balance >= 0:
            return 0
        if not self.due_date:
            return 0

        now = now or timezone.now()
        if now <= self.due_date:
            return 0

        overdue_days = (now - self.due_date).days
        if overdue_days <= 0:
            return 0

        base = abs(int(self.closing_balance))
        daily_total = int(base * STATEMENT_PENALTY_RATE * overdue_days)
        cap = int(base * STATEMENT_MAX_PENALTY_RATE)
        return min(daily_total, cap)

    def mark_overdue_if_needed(self):
        """Transition pending -> overdue when due_date is passed."""
        if self.status == StatementStatus.PENDING_PAYMENT and self.due_date and timezone.now() > self.due_date:
            self.status = StatementStatus.OVERDUE
            self.save(update_fields=["status"])

    # ---------- Interest helper (used by manager after rollover) ----------

    def add_monthly_interest_on_carryover(self, previous_stmt):
        """
        Add monthly interest line to this current statement based on previous statement's negative closing balance.
        """
        if self.status != StatementStatus.CURRENT:
            raise ValueError(
                "Interest can only be added to the current statement."
            )
        if previous_stmt.closing_balance >= 0:
            return
        interest_amount = int(
            abs(previous_stmt.closing_balance) * MONTHLY_INTEREST_RATE
        )
        self.add_line(
            StatementLineType.INTEREST, -interest_amount,
            description=f"Monthly interest on {previous_stmt.year}/{previous_stmt.month:02d}"
        )

    def save(self, *args, **kwargs):
        if not self.reference_code:
            for _ in range(5):
                self.reference_code = generate_reference_code(prefix="ST")
                try:
                    return super().save(*args, **kwargs)
                except IntegrityError:
                    self.reference_code = None
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} - {self.year}/{self.month:02d} ({self.get_status_display()})"

    class Meta:
        verbose_name = _("صورتحساب اعتباری")
        verbose_name_plural = _("صورتحساب‌های اعتباری")
        ordering = ["-year", "-month"]
        unique_together = ["user", "year", "month"]
        indexes = [
            models.Index(fields=["user", "status"], name="st_user_status_idx"),
            models.Index(fields=["due_date"], name="st_due_idx"),
        ]
