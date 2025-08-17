# credit/models/statement.py

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from wallets.models import Transaction
from credit.models.statement_line import StatementLine
from credit.utils.reference import generate_statement_reference


class StatementManager(models.Manager):
    def get_current_statement(self, user):
        """Get the user's current (active) statement"""
        return self.filter(
            user=user,
            status='current'
        ).first()
    
    def get_or_create_current_statement(self, user):
        """Get or create current statement for user"""
        current = self.get_current_statement(user)
        if current:
            return current, False
        
        # Create new current statement
        from persiantools.jdatetime import JalaliDate
        jtoday = JalaliDate.today()
        
        statement = self.create(
            user=user,
            year=jtoday.year,
            month=jtoday.month,
            status='current',
            reference_code=generate_statement_reference()
        )
        return statement, True
    
    def close_monthly_statements(self):
        """Close any open statements from past months and create new ones"""
        from persiantools.jdatetime import JalaliDate
        from django.db import transaction
        
        today = JalaliDate.today()
        
        with transaction.atomic():
            # Find all current statements from previous months
            current_statements = self.filter(status='current')
            
            for statement in current_statements:
                # Check if this statement is from a previous month
                if statement.year < today.year or (statement.year == today.year and statement.month < today.month):
                    # Close previous statement (sets closed_at & due_date)
                    statement.close_statement()

                    # Create or get current month statement
                    new_statement, created = self.get_or_create(
                        user=statement.user,
                        year=today.year,
                        month=today.month,
                        defaults={
                            'status': 'current',
                            'reference_code': generate_statement_reference()
                        }
                    )

                    # Ensure status is current
                    if not created and new_statement.status != 'current':
                        new_statement.status = 'current'
                        new_statement.save(update_fields=['status'])

                    # Transfer closing balance to new statement as a carryover line once
                    if not statement.carried_over and statement.closing_balance != 0:
                        desc = f"انتقال مانده از {statement.year}/{statement.month:02d}"
                        # carryover amount equals previous closing balance (can be negative or positive)
                        StatementLine.objects.create(
                            statement=new_statement,
                            type='carryover',
                            amount=statement.closing_balance,
                            description=desc
                        )
                        new_statement.update_balances()
                        statement.carried_over = True
                        statement.save(update_fields=['carried_over'])
    
    def create_initial_statement(self, user):
        """Create initial statement when credit limit is assigned"""
        now = timezone.now()
        jdate = timezone.datetime(now.year, now.month, 1)
        
        return self.create(
            user=user,
            year=jdate.year,
            month=jdate.month,
            status='current',
            reference_code=generate_statement_reference()
        )


class Statement(BaseModel):
    STATUS_CHOICES = [
        ('current', _('جاری')),
        ('pending_payment', _('در انتظار پرداخت')),
        ('paid', _('پرداخت شده')),
        ('overdue', _('سررسید گذشته')),
    ]

    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='statements',
        verbose_name=_('کاربر')
    )
    
    year = models.PositiveIntegerField(
        verbose_name=_('سال شمسی')
    )
    
    month = models.PositiveIntegerField(
        verbose_name=_('ماه شمسی')
    )
    
    reference_code = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_('کد پیگیری')
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='current',
        verbose_name=_('وضعیت')
    )
    
    opening_balance = models.BigIntegerField(
        default=0,
        verbose_name=_('مانده اول دوره')
    )
    
    closing_balance = models.BigIntegerField(
        default=0,
        verbose_name=_('مانده پایان دوره')
    )
    
    total_debit = models.BigIntegerField(
        default=0,
        verbose_name=_('مجموع بدهکار')
    )
    
    total_credit = models.BigIntegerField(
        default=0,
        verbose_name=_('مجموع بستانکار')
    )
    
    due_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('تاریخ سررسید')
    )
    
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('زمان پرداخت')
    )

    # --- Closing and carryover tracking ---
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('زمان بستن')
    )

    carried_over = models.BooleanField(
        default=False,
        verbose_name=_('انتقال یافته به دوره بعد')
    )
    

    objects = StatementManager()
    
    class Meta:
        verbose_name = _('صورتحساب اعتباری')
        verbose_name_plural = _('صورتحساب‌های اعتباری')
        ordering = ['-year', '-month']
        unique_together = ['user', 'year', 'month']
    
    def __str__(self):
        return f"{self.user} - {self.year}/{self.month:02d} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        if not self.reference_code:
            self.reference_code = generate_statement_reference()
        super().save(*args, **kwargs)
    
    @property
    def current_balance(self):
        """Calculate current balance based on statement lines"""
        # Purchases, fees, penalties are negative; payments are positive
        return self.closing_balance
    
    def update_balances(self):
        """Update statement balances based on statement lines atomically"""
        from django.db import transaction
        from django.db.models import Sum, Case, When, Value, IntegerField, F
        
        with transaction.atomic():
            statement = Statement.objects.select_for_update().get(pk=self.pk)
            
            # Calculate totals atomically using database aggregation
            totals = statement.lines.aggregate(
                total_debit=Sum(
                    Case(
                        When(amount__lt=0, then=-F('amount')),
                        default=Value(0),
                        output_field=IntegerField()
                    )
                ),
                total_credit=Sum(
                    Case(
                        When(amount__gt=0, then='amount'),
                        default=Value(0),
                        output_field=IntegerField()
                    )
                )
            )
            
            total_debit = totals['total_debit'] or 0
            total_credit = totals['total_credit'] or 0
            closing_balance = statement.opening_balance + total_credit - total_debit
            
            Statement.objects.filter(pk=self.pk).update(
                total_debit=total_debit,
                total_credit=total_credit,
                closing_balance=closing_balance
            )
            
            # Refresh from db to get updated values
            self.refresh_from_db()
    
    def close_statement(self):
        """Close current statement and prepare for payment"""
        from credit import settings as credit_settings
        
        self.update_balances()
        now = timezone.now()
        self.status = 'pending_payment'
        # Use user-specific grace period for due date
        try:
            grace_days = self.get_grace_period_days()
        except Exception:
            grace_days = credit_settings.PAYMENT_GRACE_PERIOD_DAYS
        self.due_date = now + timedelta(days=grace_days)
        self.closed_at = now
        self.save(update_fields=['status', 'due_date', 'closing_balance', 'closed_at'])
    
    def mark_as_paid(self):
        """Mark statement as paid"""
        self.status = 'paid'
        self.paid_at = timezone.now()
        self.save(update_fields=['status', 'paid_at'])
    
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
        if self.status == 'paid':
            return 0
            
        if not self.due_date or timezone.now() <= self.due_date:
            return 0
            
        overdue_days = (timezone.now() - self.due_date).days
        if overdue_days <= 0:
            return 0
            
        base_amount = abs(self.closing_balance)
        penalty_amount = int(base_amount * penalty_rate * overdue_days)
        max_penalty = int(base_amount * max_penalty_rate)
        
        return min(penalty_amount, max_penalty)
    
    def add_line(self, type, amount, transaction=None, description=""):
        """Add a line to the statement.
        Rules:
        - For 'current' statements: allow all line types.
        - For 'pending_payment' statements: allow only 'payment' and 'penalty'.
        - For other statuses: disallow.
        """
        if self.status != 'current':
            if self.status == 'pending_payment' and type in {'payment', 'penalty'}:
                pass
            else:
                raise ValueError("Cannot add line to non-current statement")
        StatementLine.objects.create(
            statement=self,
            type=type,
            amount=amount,
            transaction=transaction,
            description=description
        )
        self.update_balances()

    def add_transaction(self, transaction):
        """Add purchase line to statement from a transaction"""
        if self.status != 'current':
            raise ValueError("Cannot add transaction to non-current statement")
        # Assume transaction.amount is negative for purchase
        self.add_line('purchase', -abs(transaction.amount), transaction=transaction, description="خرید")

    def apply_payment(self, amount, transaction=None):
        """Add a payment line and update credit limit"""
        pay_amount = abs(int(amount))
        self.add_line('payment', pay_amount, transaction=transaction, description="پرداخت")
        # Sync with CreditLimit.release_credit(amount)
        try:
            from credit.models.credit_limit import CreditLimit
            cl = CreditLimit.objects.get_user_credit_limit(self.user)
            if cl:
                cl.release_credit(pay_amount)
        except Exception:
            # Do not block on credit limit sync
            pass

    def apply_fee(self, amount, description="کارمزد"): 
        self.add_line('fee', -abs(amount), description=description)

    def apply_penalty(self, amount, description="جریمه"): 
        self.add_line('penalty', -abs(amount), description=description)

    def apply_carryover_adjustment(self, amount, description="تعدیل انتقال"):
        """Reduce or increase carryover in the current statement. Positive amount reduces net debt."""
        if self.status != 'current':
            raise ValueError("Carryover adjustment only allowed on current statement")
        self.add_line('carryover_adjustment', abs(amount), description=description)

    def calculate_and_apply_penalty(self, penalty_rate=None, max_penalty_rate=None):
        """Calculate and apply penalty as a statement line if overdue and not already present."""
        from credit import settings as credit_settings
        
        penalty_rate = penalty_rate or credit_settings.STATEMENT_PENALTY_RATE
        max_penalty_rate = max_penalty_rate or credit_settings.STATEMENT_MAX_PENALTY_RATE
        
        penalty = self.calculate_penalty(penalty_rate, max_penalty_rate)
        if penalty > 0 and not self.lines.filter(type='penalty').exists():
            self.apply_penalty(penalty)
            self.update_balances()
        return penalty

    # --- Grace period helpers ---
    def get_grace_period_days(self) -> int:
        """Grace days for this user: per-user override via CreditLimit or default settings."""
        from credit.models.credit_limit import CreditLimit
        from credit import settings as credit_settings
        cl = CreditLimit.objects.get_user_credit_limit(self.user)
        return cl.get_grace_period_days() if cl else int(credit_settings.PAYMENT_GRACE_PERIOD_DAYS)

    @property
    def grace_ends_at(self):
        if not self.closed_at:
            return None
        return self.closed_at + timedelta(days=self.get_grace_period_days())

    def is_within_grace(self, now=None) -> bool:
        """Return True if now is within grace window after statement closure."""
        if not self.closed_at:
            return False
        now = now or timezone.now()
        end = self.grace_ends_at
        return end is not None and now <= end
