# credit/models/credit_limit.py

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from credit.utils.constants import STATEMENT_GRACE_DAYS
from utils.reference import generate_reference_code
from lib.erp_base.models import BaseModel


class CreditLimitManager(models.Manager):
    def get_user_credit_limit(self, user):
        return self.filter(
            user=user,
            is_active=True,
            expiry_date__gt=timezone.localdate()
        ).first()

    def get_available_credit(self, user):
        """Calculate available credit for user"""
        credit_limit = self.get_user_credit_limit(user)
        return credit_limit.available_limit if credit_limit else 0


class CreditLimit(BaseModel):
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="credit_limits",
        verbose_name=_("کاربر"),
    )

    approved_limit = models.BigIntegerField(
        verbose_name=_("حد اعتباری تایید شده")
    )

    is_active = models.BooleanField(default=False, verbose_name=_("فعال"))

    # Optional per-user grace period override (in days). If null, use default from settings.
    grace_period_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("مهلت پرداخت (روز)")
    )

    expiry_date = models.DateField(verbose_name=_("تاریخ انقضا"))

    reference_code = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_("کد پیگیری")
    )

    objects = CreditLimitManager()

    def save(self, *args, **kwargs):
        if not self.reference_code:
            for _ in range(5):
                self.reference_code = generate_reference_code(prefix="CR")
                try:
                    return super().save(*args, **kwargs)
                except IntegrityError:
                    self.reference_code = None
        return super().save(*args, **kwargs)

    @property
    def is_approved(self) -> bool:
        return True

    @property
    def available_limit(self) -> int:
        """approved_limit - sum(active debts)"""
        debt = self._current_active_debt()
        return max(0, int(self.approved_limit) - debt)

    @property
    def grace_days(self) -> int:
        return int(
            self.grace_period_days
        ) if self.grace_period_days is not None else int(
            STATEMENT_GRACE_DAYS
        )

    def _current_active_debt(self) -> int:
        from credit.models.statement import Statement
        from credit.utils.choices import StatementStatus
        agg = (
            Statement.objects.filter(
                user=self.user,
                status=StatementStatus.CURRENT,
                closing_balance__lt=0,
            )
            .aggregate(total=models.Sum(models.F("closing_balance")))
        )
        total_negative = agg["total"] or 0
        return abs(int(total_negative))

    def activate(self):
        with transaction.atomic():
            CreditLimit.objects.filter(user=self.user, is_active=True).update(
                is_active=False, updated_at=timezone.now()
            )
            self.is_active = True
            self.save(update_fields=["is_active", "updated_at"])

    @classmethod
    def deactivate_user_active_limits(cls, user):
        return cls.objects.filter(user=user, is_active=True).update(
            is_active=False, updated_at=timezone.now()
        )

    def __str__(self):
        return f"{self.user} - {self.approved_limit:,} ریال"

    class Meta:
        verbose_name = _("حد اعتباری")
        verbose_name_plural = _("حدود اعتباری")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_active=True),
                name="unique_active_credit_limit_per_user",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "is_active"], name="cl_user_active_idx"
            ),
            models.Index(fields=["expiry_date"], name="cl_expiry_idx"),
        ]
