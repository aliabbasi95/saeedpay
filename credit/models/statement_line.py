# credit/models/statement_line.py

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction as db_transaction
from django.utils import timezone
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
        max_length=255,
        blank=True,
        verbose_name=_("توضیحات")
    )

    # --- audit / soft-delete / reversal ---
    is_voided = models.BooleanField(
        default=False, db_index=True, verbose_name=_("باطل‌شده")
    )
    voided_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("زمان ابطال")
    )
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="voided_statement_lines",
        verbose_name=_("ابطال‌کننده"),
    )
    void_reason = models.CharField(
        max_length=255, blank=True, verbose_name=_("دلیل ابطال")
    )
    reverses = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversed_by",
        verbose_name=_("معکوسِ سطر"),
    )

    # managers
    class ActiveLineManager(models.Manager):
        def get_queryset(self):
            return super().get_queryset().filter(is_voided=False)

    objects = ActiveLineManager()
    all_objects = models.Manager()

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
                                   Transaction.objects.filter(
                                       pk=self.transaction_id
                                   )
                                   .values_list(
                                       "from_wallet__user_id",
                                       "to_wallet__user_id"
                                   )
                                   .first()
                               ) or (None, None)
            from_user_id, to_user_id = from_to_user_ids
            if self.statement.user_id not in {from_user_id, to_user_id}:
                errors["transaction"] = _(
                    "Transaction does not belong to the statement user."
                )

        # allowed types by statement status
        if self.statement_id:
            statement_obj = self.statement
            if self.type in {
                StatementLineType.PURCHASE,
                StatementLineType.FEE,
                StatementLineType.INTEREST
            }:
                if statement_obj.status != StatementStatus.CURRENT:
                    errors["type"] = _(
                        "This line type is only allowed on CURRENT statements."
                    )
            elif self.type == StatementLineType.PAYMENT:
                if statement_obj.status != StatementStatus.CURRENT:
                    errors["type"] = _(
                        "Payments are only allowed on CURRENT statements."
                    )
            elif self.type == StatementLineType.PENALTY:
                if statement_obj.status != StatementStatus.CURRENT:
                    errors["type"] = _(
                        "Penalty lines should be added to the CURRENT statement."
                    )

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

        amount_changed_by_normalization = self.amount != amount_value

        # model-level validation (includes clean())
        self.full_clean()
        if kwargs.get("update_fields") is not None:
            ufs = set(kwargs["update_fields"])
            if amount_changed_by_normalization:
                ufs.add("amount")
            kwargs["update_fields"] = list(ufs)

        super().save(*args, **kwargs)

        # recompute parent balances when needed (only non-voided lines affect totals)
        update_fields = kwargs.get("update_fields")
        should_recompute = (
                is_new
                or update_fields is None
                or any(field in update_fields for field in ("amount", "type"))
        )
        if should_recompute and self.statement_id:
            self.statement.update_balances()

    # ---------- lifecycle: forbid hard delete ----------
    def delete(self, *args, **kwargs):
        raise ValidationError(
            _(
                "Deleting statement lines is not allowed. Use void() or reverse()."
            )
        )

    # ---------- lifecycle: void / reverse ----------
    @db_transaction.atomic
    def void(self, by=None, reason: str = "") -> bool:
        if self.is_voided:
            return False
        self.is_voided = True
        self.voided_at = timezone.now()
        self.voided_by = by
        self.void_reason = (reason or "")[:255]
        super().save(
            update_fields=["is_voided", "voided_at", "voided_by",
                           "void_reason"]
        )
        if self.statement_id:
            self.statement.update_balances()
        return True

    @db_transaction.atomic
    def reverse(self, by=None, reason: str = ""):
        if self.is_voided:
            raise ValidationError(_("Cannot reverse a voided line."))
        if self.reversed_by.exists():
            raise ValidationError(_("This line is already reversed."))

        # pick reverse type/amount
        if self.type in self._debit_types():  # amount < 0
            rev_type = StatementLineType.PAYMENT  # positive
            rev_amount = abs(int(self.amount))
        else:  # PAYMENT (amount > 0)
            rev_type = StatementLineType.PURCHASE  # negative
            rev_amount = -abs(int(self.amount))

        rev = StatementLine.all_objects.create(
            statement=self.statement,
            type=rev_type,
            amount=rev_amount,
            description=(f"Reversal of line {self.pk}: {reason}"[
                             :255] if reason else f"Reversal of line {self.pk}"),
            reverses=self,
        )
        if self.statement_id:
            self.statement.update_balances()
        return rev

    def __str__(self):
        return f"{self.get_type_display()} | {self.amount} | {self.created_at.date()}"

    class Meta:
        verbose_name = _("سطر صورتحساب")
        verbose_name_plural = _("سطرهای صورتحساب")
        ordering = ["created_at"]
        constraints = [
            # only one interest line per statement (among active lines)
            models.UniqueConstraint(
                fields=["statement", "type"],
                condition=models.Q(
                    type=StatementLineType.INTEREST, is_voided=False
                ),
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
            models.Index(fields=["is_voided"], name="stl_void_idx"),
        ]
