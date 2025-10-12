# wallets/models/installment.py

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from wallets.models import InstallmentPlan, Transaction
from wallets.utils.choices import InstallmentStatus


class Installment(BaseModel):
    plan = models.ForeignKey(
        InstallmentPlan,
        on_delete=models.CASCADE,
        related_name="installments",
        verbose_name=_("برنامه اقساط")
    )

    due_date = models.DateField(verbose_name=_("تاریخ سررسید"))
    amount = models.BigIntegerField(verbose_name=_("مبلغ قسط"))
    amount_paid = models.BigIntegerField(
        default=0, verbose_name=_("مبلغ پرداخت‌شده")
    )
    penalty_amount = models.BigIntegerField(
        default=0, verbose_name=_("جریمه پرداخت‌شده")
    )

    status = models.CharField(
        max_length=16,
        choices=InstallmentStatus.choices,
        default=InstallmentStatus.UNPAID,
        verbose_name=_("وضعیت")
    )

    paid_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("زمان پرداخت")
    )

    transaction = models.ForeignKey(
        Transaction,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="installments",
        verbose_name=_("تراکنش پرداخت")
    )

    note = models.TextField(blank=True, verbose_name=_("یادداشت"))

    @property
    def is_overdue(self) -> bool:
        return self.status == InstallmentStatus.UNPAID and self.due_date < timezone.localtime(
            timezone.now()
            ).date()

    @property
    def current_penalty(self) -> int:
        return self.calculate_penalty()

    def calculate_penalty(self, daily_rate: float = 0.005) -> int:
        if self.status == InstallmentStatus.PAID:
            return self.penalty_amount
        today = timezone.localtime(timezone.now()).date()
        if self.due_date >= today:
            return 0
        overdue_days = (today - self.due_date).days
        return int(self.amount * daily_rate * overdue_days)

    def mark_paid(
            self, amount_paid: int, penalty_paid: int, transaction: Transaction
    ):
        self.amount_paid = amount_paid
        self.penalty_amount = penalty_paid
        self.transaction = transaction
        self.paid_at = timezone.localtime(timezone.now())
        self.status = InstallmentStatus.PAID
        self.save()

    def __str__(self):
        return f"Installment #{self.id} - {self.amount} due on {self.due_date}"

    class Meta:
        ordering = ["due_date"]
        indexes = [
            models.Index(
                fields=["plan", "due_date"], name="inst_plan_due_idx"
            ),
            models.Index(fields=["status"], name="inst_status_idx"),
        ]
        verbose_name = _("قسط")
        verbose_name_plural = _("اقساط")
