# wallets/models/payment.py

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from utils.reference import generate_reference_code
from wallets.models.wallet import Wallet
from wallets.utils.choices import PaymentFlowType, PaymentMethod, PaymentStatus


class Payment(BaseModel):
    payment_request = models.ForeignKey(
        "wallets.PaymentRequest",
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name=_("درخواست پرداخت"),
    )
    payer = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name=_("پرداخت‌کننده"),
    )
    payer_wallet = models.ForeignKey(
        Wallet,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payments",
        verbose_name=_("کیف پول پرداخت‌کننده"),
    )
    amount = models.BigIntegerField(verbose_name=_("مبلغ"))
    method = models.CharField(
        max_length=16,
        choices=PaymentMethod.choices,
        verbose_name=_("روش پرداخت"),
    )
    flow_type = models.CharField(
        max_length=16,
        choices=PaymentFlowType.choices,
        verbose_name=_("نوع جریان"),
    )
    status = models.CharField(
        max_length=32,
        choices=PaymentStatus.choices,
        default=PaymentStatus.CREATED,
        db_index=True,
        verbose_name=_("وضعیت"),
    )
    reference_code = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_("کد پیگیری"),
    )
    authorization_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("انقضای مجوز/هولد"),
    )
    merchant_confirm_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("انقضای تایید فروشگاه"),
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("زمان تکمیل"),
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("زمان لغو"),
    )
    expired_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("زمان انقضا"),
    )
    failure_reason = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("دلیل خطا"),
    )

    def save(self, *args, **kwargs):
        if not self.reference_code:
            for _ in range(5):
                code = generate_reference_code(prefix="PAY", random_digits=6)
                if not Payment.objects.filter(reference_code=code).exists():
                    self.reference_code = code
                    break
            else:
                raise Exception("Payment reference code generation failed.")
        super().save(*args, **kwargs)

    @property
    def operation_reference_code(self) -> str:
        last_transaction = self.transactions.order_by("-created_at", "-id").first()
        if last_transaction:
            return last_transaction.reference_code

        credit_authorizations = getattr(self, "credit_authorizations", None)
        if credit_authorizations is not None:
            auth = credit_authorizations.order_by("-created_at", "-id").first()
            if auth:
                return auth.reference_code

        return self.reference_code or ""

    def __str__(self):
        return (
            f"{self.reference_code or self.pk} | "
            f"{self.get_method_display()} | "
            f"{self.amount}"
        )

    class Meta:
        verbose_name = _("پرداخت")
        verbose_name_plural = _("پرداخت‌ها")
        indexes = [
            models.Index(
                fields=["payment_request", "status"],
                name="pay_pr_status_idx",
            ),
            models.Index(
                fields=["payer", "status"],
                name="pay_payer_status_idx",
            ),
            models.Index(
                fields=["flow_type", "status"],
                name="pay_flow_status_idx",
            ),
        ]
