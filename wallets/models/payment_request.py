# wallets/models/payment.py

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from customers.models import Customer
from lib.erp_base.models import BaseModel
from store.models import Store
from utils.reference import generate_reference_code
from wallets.models.wallet import Wallet
from wallets.utils.choices import PaymentRequestStatus
from wallets.utils.consts import PAYMENT_REQUEST_EXPIRY_MINUTES


class PaymentRequest(BaseModel):
    store = models.ForeignKey(
        Store,
        null=True,
        on_delete=models.CASCADE,
        related_name="payment_requests",
        verbose_name=_("فروشگاه درخواست‌دهنده")
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE,
        null=True,
        related_name="payment_requests",
        verbose_name=_("مشتری")
    )
    status = models.CharField(
        max_length=32,
        choices=PaymentRequestStatus.choices,
        default=PaymentRequestStatus.CREATED,
        verbose_name=_("وضعیت"),
    )
    reference_code = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name="کد پیگیری"
    )
    external_guid = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        verbose_name=_("شناسه بیرونی (external_guid)"),
        help_text=_("شناسهٔ یکتا از سمت فروشگاه/سیستم بیرونی")
    )
    amount = models.BigIntegerField(
        verbose_name=_("مبلغ")
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("توضیحات")
    )
    return_url = models.URLField(
        blank=False,
        null=False,
        verbose_name=_("آدرس بازگشت (return_url)")
    )
    paid_by = models.ForeignKey(
        get_user_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="successful_payments",
        verbose_name=_("پرداخت‌کننده")
    )
    paid_wallet = models.ForeignKey(
        Wallet,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("کیف پول پرداخت‌کننده")
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("تاریخ انقضا")
    )
    created_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="ددلاین فاز CREATED"
    )
    merchant_confirm_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="ددلاین تایید مرچنت"
    )

    paid_at = models.DateTimeField(null=True, blank=True)

    def mark_awaiting_merchant(self):
        self.status = PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        self.save(update_fields=["status"])

    def mark_completed(self):
        self.status = PaymentRequestStatus.COMPLETED
        self.save(update_fields=["status"])

    def mark_cancelled(self):
        self.status = PaymentRequestStatus.CANCELLED
        self.save(update_fields=["status"])
        from wallets.services.payment import rollback_payment
        rollback_payment(self)

    def mark_expired(self):
        self.status = PaymentRequestStatus.EXPIRED
        self.save(update_fields=["status"])
        from wallets.services.payment import rollback_payment
        rollback_payment(self)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(
                minutes=PAYMENT_REQUEST_EXPIRY_MINUTES
            )
        if not self.reference_code:
            for _ in range(5):
                code = generate_reference_code(prefix="PR", random_digits=6)
                if not PaymentRequest.objects.filter(
                        reference_code=code
                ).exists():
                    self.reference_code = code
                    break
            else:
                raise Exception(
                    "Reference code generation failed. Please try again."
                )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"درخواست پرداخت #{self.id} - {self.amount} ریال - فروشگاه {self.store.name}"

    class Meta:
        verbose_name = _("درخواست پرداخت")
        verbose_name_plural = _("درخواست‌های پرداخت")
        indexes = [
            models.Index(
                fields=["customer", "-created_at"], name="pr_cust_created_idx"
            ),
            models.Index(fields=["status"], name="pr_status_idx"),
            models.Index(fields=["expires_at"], name="pr_expires_idx"),
            models.Index(
                fields=["store", "status"], name="pr_store_status_idx"
            ),
            models.Index(fields=["reference_code"], name="pr_ref_idx"),
            models.Index(
                fields=["store", "external_guid"], name="pr_store_ext_idx"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["store", "external_guid"],
                name="uniq_store_external_guid",
                condition=models.Q(external_guid__isnull=False),
            ),
        ]
