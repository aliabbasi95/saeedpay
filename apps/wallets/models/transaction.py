# apps/wallets/models/transaction.py

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.wallets.models.wallet import Wallet
from apps.wallets.utils.choices import TransactionPurpose, TransactionStatus
from lib.erp_base.models import BaseModel
from utils.reference import generate_reference_code


class Transaction(BaseModel):
    reference_code = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_("کد پیگیری"),
    )
    status = models.CharField(
        max_length=16,
        choices=TransactionStatus.choices,
        default=TransactionStatus.PENDING,
        verbose_name=_("وضعیت"),
    )
    purpose = models.CharField(
        max_length=32,
        choices=TransactionPurpose.choices,
        verbose_name=_("نوع عملیات"),
        db_index=True,
        null=True,
        blank=True,
    )
    payment = models.ForeignKey(
        "wallets.Payment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions",
        verbose_name=_("پرداخت مرتبط"),
    )
    related_transaction = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="child_transactions",
        verbose_name=_("تراکنش مرتبط"),
    )
    from_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="outgoing_transactions",
        verbose_name=_("از کیف پول"),
    )
    to_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="incoming_transactions",
        verbose_name=_("به کیف پول"),
    )
    amount = models.BigIntegerField(verbose_name=_("مبلغ"))
    payment_request = models.ForeignKey(
        "wallets.PaymentRequest",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("درخواست پرداخت"),
    )
    description = models.TextField(blank=True)

    @classmethod
    def create_success(
        cls,
        *,
        from_wallet,
        to_wallet,
        amount,
        purpose,
        payment=None,
        payment_request=None,
        description="",
        related_transaction=None,
    ):
        return cls.objects.create(
            from_wallet=from_wallet,
            to_wallet=to_wallet,
            amount=amount,
            purpose=purpose,
            status=TransactionStatus.SUCCESS,
            payment=payment,
            payment_request=payment_request,
            description=description,
            related_transaction=related_transaction,
        )

    @classmethod
    def latest_success_for_payment(cls, payment, purpose):
        return (
            cls.objects.filter(
                payment=payment,
                purpose=purpose,
                status=TransactionStatus.SUCCESS,
            )
            .order_by("-created_at", "-id")
            .first()
        )

    @classmethod
    def success_exists_for_payment(cls, payment, purpose):
        return cls.objects.filter(
            payment=payment,
            purpose=purpose,
            status=TransactionStatus.SUCCESS,
        ).exists()

    def save(self, *args, **kwargs):
        if not self.reference_code:
            for _ in range(5):
                code = generate_reference_code(prefix="TRX", random_digits=6)
                if not Transaction.objects.filter(reference_code=code).exists():
                    self.reference_code = code
                    break
            else:
                raise Exception("Transaction reference code generation failed.")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference_code or self.pk} | {self.amount}"

    class Meta:
        verbose_name = _("تراکنش کیف پول")
        verbose_name_plural = _("تراکنش‌های کیف پول")
        indexes = [
            models.Index(
                fields=["payment_request", "purpose", "status"],
                name="trx_pr_purpose_status_idx",
            ),
            models.Index(
                fields=["from_wallet_id", "to_wallet_id"],
                name="trx_from_to_idx",
            ),
            models.Index(
                fields=["payment", "purpose", "status"],
                name="trx_payment_purpose_status_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name="trx_amount_gt_zero",
            ),
        ]
