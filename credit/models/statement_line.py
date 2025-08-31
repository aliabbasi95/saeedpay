# credit/models/statement_line.py

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from credit.utils.choices import StatementLineType, StatementStatus
from lib.erp_base.models import BaseModel
from wallets.models import Transaction


class StatementLine(BaseModel):
    statement = models.ForeignKey(
        "credit.Statement",
        related_name="lines",
        on_delete=models.CASCADE,
        verbose_name=_("صورتحساب"),
    )
    type = models.CharField(
        max_length=20,
        choices=StatementLineType.choices,
        verbose_name=_("نوع سطر"),
    )
    amount = models.BigIntegerField(verbose_name=_("مبلغ"))
    transaction = models.ForeignKey(
        Transaction,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("تراکنش مرتبط"),
    )
    description = models.CharField(
        max_length=255, blank=True, verbose_name=_("توضیحات")
    )

    # ---------- helpers ----------
    @staticmethod
    def _debit_types():
        return {
            StatementLineType.PURCHASE,
            StatementLineType.FEE,
            StatementLineType.PENALTY,
            StatementLineType.INTEREST,
        }

    @staticmethod
    def _credit_types():
        return {StatementLineType.PAYMENT}

    # ---------- validations ----------
    def clean(self):
        errors = {}

        # amount must be non-zero
        if int(self.amount or 0) == 0:
            errors["amount"] = _("Amount cannot be zero.")

        # transaction must belong to statement user
        if self.transaction_id and self.statement_id:
            from_to_user_ids = (
                Transaction.objects.filter(pk=self.transaction_id)
                .values_list("from_wallet__user_id", "to_wallet__user_id")
                .first()
            ) or (None, None)
            from_user_id, to_user_id = from_to_user_ids
            if self.statement.user_id not in {from_user_id, to_user_id}:
                errors["transaction"] = _("Transaction does not belong to the statement user.")

        # allowed types by statement status
        if self.statement_id:
            statement_obj = self.statement
            if self.type in {StatementLineType.PURCHASE, StatementLineType.FEE, StatementLineType.INTEREST}:
                if statement_obj.status != StatementStatus.CURRENT:
                    errors["type"] = _("This line type is only allowed on CURRENT statements.")
            elif self.type == StatementLineType.PAYMENT:
                if statement_obj.status != StatementStatus.CURRENT:
                    errors["type"] = _("Payments are only allowed on CURRENT statements.")
            elif self.type == StatementLineType.PENALTY:
                if statement_obj.status != StatementStatus.CURRENT:
                    errors["type"] = _("Penalty lines should be added to the CURRENT statement.")

        if errors:
            raise ValidationError(errors)

    # ---------- persistence ----------
    def save(self, *args, **kwargs):
        is_new = self.pk is None

        # normalize sign by type
        amount_value = int(self.amount or 0)
        if self.type in self._debit_types() and amount_value > 0:
            self.amount = -abs(amount_value)
        elif self.type in self._credit_types() and amount_value < 0:
            self.amount = abs(amount_value)

        # model-level validation (includes clean())
        self.full_clean()
        super().save(*args, **kwargs)

        # recompute parent balances when needed
        update_fields = kwargs.get("update_fields")
        should_recompute = (
            is_new
            or update_fields is None
            or any(field in update_fields for field in ("amount", "type"))
        )
        if should_recompute and self.statement_id:
            self.statement.update_balances()

    def __str__(self):
        return f"{self.get_type_display()} | {self.amount} | {self.created_at.date()}"

    class Meta:
        verbose_name = _("سطر صورتحساب")
        verbose_name_plural = _("سطرهای صورتحساب")
        ordering = ["created_at"]
        constraints = [
            # only one interest line per statement
            models.UniqueConstraint(
                fields=["statement", "type"],
                condition=models.Q(type=StatementLineType.INTEREST),
                name="uniq_interest_per_statement",
            ),
            # hard DB-level sign guard: payments > 0, charges < 0
            models.CheckConstraint(
                name="amount_sign_by_type",
                check=(
                    models.Q(type=StatementLineType.PAYMENT, amount__gt=0)
                    | models.Q(
                        type__in=[
                            StatementLineType.PURCHASE,
                            StatementLineType.FEE,
                            StatementLineType.PENALTY,
                            StatementLineType.INTEREST,
                        ],
                        amount__lt=0,
                    )
                ),
            ),
        ]
        indexes = [
            models.Index(
                fields=["statement", "created_at"], name="stl_stmt_created_idx"
            ),
            models.Index(fields=["type"], name="stl_type_idx"),
        ]
