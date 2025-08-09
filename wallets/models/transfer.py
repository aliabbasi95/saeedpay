# wallets/models/transfer.py

from django.db import models
from django.utils import timezone

from lib.erp_base.models import BaseModel
from wallets.models.transaction import Transaction
from wallets.models.wallet import Wallet
from wallets.utils.choices import TransferStatus
from wallets.utils.reference import generate_reference_code


class WalletTransferRequest(BaseModel):
    transaction = models.OneToOneField(
        Transaction,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transfer_request",
        verbose_name="تراکنش"
    )
    reference_code = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name="کد پیگیری"
    )
    sender_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="sent_transfers",
        verbose_name="کیف مبدا"
    )
    receiver_wallet = models.ForeignKey(
        Wallet,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="received_transfers",
        verbose_name="کیف مقصد"
    )
    receiver_phone_number = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        verbose_name="شماره موبایل مقصد"
    )
    amount = models.BigIntegerField(verbose_name="مبلغ")
    description = models.CharField(
        max_length=255, blank=True, verbose_name="توضیحات"
    )
    status = models.CharField(
        max_length=32, choices=TransferStatus.choices,
        default=TransferStatus.PENDING_CONFIRMATION, verbose_name="وضعیت"
    )
    expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name="انقضا"
    )

    def save(self, *args, **kwargs):
        if not self.reference_code:
            for _ in range(5):
                code = generate_reference_code(prefix="WT", random_digits=6)
                if not WalletTransferRequest.objects.filter(
                        reference_code=code
                ).exists():
                    self.reference_code = code
                    break
            else:
                raise Exception(
                    "Reference code generation failed. Please try again."
                )
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=1)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"انتقال از {self.sender_wallet} به {self.receiver_wallet or self.receiver_phone_number} - {self.amount} ریال"

    class Meta:
        verbose_name = "درخواست انتقال کیف"
        verbose_name_plural = "درخواست‌های انتقال کیف"
        indexes = [
            models.Index(fields=["sender_wallet"]),
            models.Index(fields=["receiver_wallet"]),
            models.Index(fields=["receiver_phone_number"]),
            models.Index(fields=["reference_code"]),
            models.Index(fields=["status"]),
        ]
