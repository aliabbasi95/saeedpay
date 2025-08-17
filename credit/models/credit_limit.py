# credit/models/credit_limit.py

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db import IntegrityError

from lib.erp_base.models import BaseModel
from credit.utils.reference import generate_credit_reference


class CreditLimitManager(models.Manager):
    def get_user_credit_limit(self, user):
        """Get active credit limit for user"""
        return self.filter(
            user=user,
            status='active',
            expiry_date__gt=timezone.localdate()
        ).first()

    def get_available_credit(self, user):
        """Calculate available credit for user"""
        credit_limit = self.get_user_credit_limit(user)
        if not credit_limit:
            return 0
        return credit_limit.available_limit


class CreditLimit(BaseModel):
    STATUS_CHOICES = [
        ('active', _('فعال')),
        ('suspended', _('تعلیق شده')),
        ('expired', _('منقضی شده')),
    ]

    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='credit_limits',
        verbose_name=_('کاربر')
    )
    
    approved_limit = models.BigIntegerField(
        verbose_name=_('حد اعتباری تایید شده')
    )
    

    
    used_limit = models.BigIntegerField(
        default=0,
        verbose_name=_('اعتبار استفاده شده')
    )

    # Optional per-user grace period override (in days). If null, use default from settings.
    grace_period_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('مهلت پرداخت (روز)')
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name=_('وضعیت')
    )
    
    expiry_date = models.DateField(
        verbose_name=_('تاریخ انقضا')
    )
    
    reference_code = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_('کد پیگیری')
    )
    
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('زمان تایید')
    )
    
    objects = CreditLimitManager()
    
    class Meta:
        verbose_name = _('حد اعتباری')
        verbose_name_plural = _('حدود اعتباری')
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(status='active'),
                name='unique_active_credit_limit_per_user'
            )
        ]
        indexes = [
            models.Index(fields=['user', 'status'], name='cl_user_status_idx'),
            models.Index(fields=['expiry_date'], name='cl_expiry_idx'),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.approved_limit:,} ریال"
    
    def save(self, *args, **kwargs):
        if not self.reference_code:
            # Retry a few times to avoid rare collisions
            for _ in range(5):
                self.reference_code = generate_credit_reference()
                try:
                    return super().save(*args, **kwargs)
                except IntegrityError:
                    # regenerate and retry
                    self.reference_code = None
            # If still failing, let it raise on final save
        return super().save(*args, **kwargs)
    
    @property
    def available_limit(self):
        """Calculate available credit limit dynamically"""
        return self.approved_limit - self.used_limit
    
    def get_grace_period_days(self) -> int:
        """Return effective grace period days for this user (fallback to settings)."""
        from credit import settings as credit_settings
        return int(self.grace_period_days) if self.grace_period_days is not None else int(credit_settings.PAYMENT_GRACE_PERIOD_DAYS)
    
    def use_credit(self, amount):
        """Use credit amount and update limits atomically"""
        from django.db import transaction
        from django.db.models import F
        
        amount = int(amount)
        if amount <= 0:
            raise ValueError("مبلغ نامعتبر است")

        with transaction.atomic():
            credit_limit = CreditLimit.objects.select_for_update().get(pk=self.pk)
            
            # Validate status and expiry
            if credit_limit.status != 'active':
                raise ValueError("حد اعتباری غیرفعال است")
            if credit_limit.expiry_date <= timezone.localdate():
                raise ValueError("حد اعتباری منقضی شده است")

            if amount > credit_limit.available_limit:
                raise ValueError("مبلغ بیشتر از اعتبار موجود است")
            
            CreditLimit.objects.filter(pk=self.pk).update(
                used_limit=F('used_limit') + amount
            )
            
            # Refresh from db to get updated values
            self.refresh_from_db()
    
    def release_credit(self, amount):
        """Release used credit amount atomically"""
        from django.db import transaction
        from django.db.models import F
        
        amount = int(amount)
        if amount <= 0:
            raise ValueError("مبلغ نامعتبر است")

        with transaction.atomic():
            credit_limit = CreditLimit.objects.select_for_update().get(pk=self.pk)
            # Clamp release to current used amount
            release_amount = min(amount, max(0, int(credit_limit.used_limit)))
            if release_amount == 0:
                # Nothing to release
                return
            CreditLimit.objects.filter(pk=self.pk).update(
                used_limit=F('used_limit') - release_amount
            )
            # Refresh from db to get updated values
            self.refresh_from_db()
