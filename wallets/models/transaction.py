# wallets/models/transaction.py

from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from utils.reference import generate_reference_code
from wallets.models import Wallet
from wallets.utils.choices import TransactionStatus, TransactionPurpose


class Transaction(BaseModel):
    reference_code = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name="کد پیگیری"
    )
    status = models.CharField(
        max_length=16,
        choices=TransactionStatus.choices,
        default=TransactionStatus.PENDING,
        verbose_name=_("وضعیت")
    )
    purpose = models.CharField(
        max_length=32,
        choices=TransactionPurpose.choices,
        verbose_name=_("نوع عملیات"),
        db_index=True,
        null=True
    )
    from_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="outgoing_transactions",
        verbose_name=_("از کیف پول")
    )
    to_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="incoming_transactions",
        verbose_name=_("به کیف پول")
    )
    amount = models.BigIntegerField(verbose_name=_("مبلغ"))
    payment_request = models.ForeignKey(
        "wallets.PaymentRequest",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("درخواست پرداخت")
    )
    description = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.reference_code:
            for _ in range(5):
                code = generate_reference_code(prefix="TRX", random_digits=6)
                if not Transaction.objects.filter(
                        reference_code=code
                ).exists():
                    self.reference_code = code
                    break
            else:
                raise Exception(
                    "Reference code generation failed. Please try again."
                )
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("تراکنش کیف پول")
        verbose_name_plural = _("تراکنش‌های کیف پول")
        indexes = [
            models.Index(
                fields=["payment_request", "purpose", "status"],
                name="trx_pr_purpose_status_idx"
            ),
            models.Index(
                fields=["from_wallet_id", "to_wallet_id"],
                name="trx_from_to_idx"
            ),
        ]
        constraints = [
            # amount must be positive
            models.CheckConstraint(
                check=models.Q(amount__gt=0), name="trx_amount_gt_zero"
            ),
        ]
