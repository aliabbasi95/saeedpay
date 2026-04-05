# wallets/models/payment_request.py

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from customers.models import Customer
from lib.erp_base.models import BaseModel
from store.models import Store
from utils.reference import generate_reference_code
from wallets.models.wallet import Wallet
from wallets.utils.choices import PaymentFlowType, PaymentRequestStatus
from wallets.utils.consts import PAYMENT_REQUEST_EXPIRY_MINUTES


def rollback_payment(payment_request):
    """
    Patchable model-level rollback hook.

    This keeps the model decoupled from service imports at import time and
    avoids circular imports. The actual service function is imported lazily.
    """
    from wallets.services.payment import rollback_payment as service_rollback_payment

    payment = payment_request.payments.order_by("-created_at", "-id").first()
    if payment is None:
        return None

    return service_rollback_payment(payment)


class PaymentRequest(BaseModel):
    store = models.ForeignKey(
        Store,
        null=True,
        on_delete=models.CASCADE,
        related_name="payment_requests",
        verbose_name=_("فروشگاه درخواست‌دهنده"),
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="payment_requests",
        verbose_name=_("مشتری"),
    )
    flow_type = models.CharField(
        max_length=16,
        choices=PaymentFlowType.choices,
        default=PaymentFlowType.ONLINE,
        verbose_name=_("نوع جریان"),
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
        verbose_name=_("کد پیگیری"),
    )
    external_guid = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        verbose_name=_("شناسه بیرونی"),
        help_text=_("شناسه یکتای سمت فروشگاه/سیستم بیرونی"),
    )
    amount = models.BigIntegerField(verbose_name=_("مبلغ"))
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("توضیحات"),
    )
    return_url = models.URLField(
        blank=False,
        null=False,
        verbose_name=_("آدرس بازگشت"),
    )
    paid_by = models.ForeignKey(
        get_user_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="successful_payments",
        verbose_name=_("پرداخت‌کننده"),
    )
    paid_wallet = models.ForeignKey(
        Wallet,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("کیف پول پرداخت‌کننده"),
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("تاریخ انقضا"),
    )
    created_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("ددلاین فاز created"),
    )
    merchant_confirm_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("ددلاین تایید فروشگاه"),
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)

    def mark_awaiting_merchant(self):
        self.status = PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        self.save(update_fields=["status"])

    def mark_completed(self):
        self.status = PaymentRequestStatus.COMPLETED
        if not self.completed_at:
            self.completed_at = timezone.localtime(timezone.now())
        self.save(update_fields=["status", "completed_at"])

    def mark_cancelled(self):
        self.status = PaymentRequestStatus.CANCELLED
        if not self.cancelled_at:
            self.cancelled_at = timezone.localtime(timezone.now())
        self.save(update_fields=["status", "cancelled_at"])

        rollback_payment(self)

    def mark_expired(self):
        self.status = PaymentRequestStatus.EXPIRED
        if not self.expired_at:
            self.expired_at = timezone.localtime(timezone.now())
        self.save(update_fields=["status", "expired_at"])

        rollback_payment(self)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.localtime(
                timezone.now()
            ) + timezone.timedelta(minutes=PAYMENT_REQUEST_EXPIRY_MINUTES)

        if not self.reference_code:
            for _ in range(5):
                code = generate_reference_code(prefix="PR", random_digits=6)
                if not PaymentRequest.objects.filter(reference_code=code).exists():
                    self.reference_code = code
                    break
            else:
                raise Exception(
                    "Payment request reference code generation failed."
                )

        super().save(*args, **kwargs)

    def __str__(self):
        store_name = getattr(self.store, "name", "-")
        return f"درخواست پرداخت #{self.id} - {self.amount} ریال - {store_name}"

    class Meta:
        verbose_name = _("درخواست پرداخت")
        verbose_name_plural = _("درخواست‌های پرداخت")
        indexes = [
            models.Index(
                fields=["customer", "-created_at"],
                name="pr_cust_created_idx",
            ),
            models.Index(fields=["status"], name="pr_status_idx"),
            models.Index(fields=["expires_at"], name="pr_expires_idx"),
            models.Index(
                fields=["store", "status"],
                name="pr_store_status_idx",
            ),
            models.Index(fields=["reference_code"], name="pr_ref_idx"),
            models.Index(
                fields=["store", "external_guid"],
                name="pr_store_ext_idx",
            ),
            models.Index(
                fields=["flow_type", "status"],
                name="pr_flow_status_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["store", "external_guid"],
                name="uniq_store_external_guid",
                condition=models.Q(external_guid__isnull=False),
            ),
        ]
