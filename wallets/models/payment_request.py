# wallets/models/payment_request.py

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
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


class PaymentRequest(BaseModel):
    ALLOWED_STATUS_TRANSITIONS = {
        PaymentRequestStatus.CREATED: {
            PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION,
            PaymentRequestStatus.CANCELLED,
            PaymentRequestStatus.EXPIRED,
        },
        PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION: {
            PaymentRequestStatus.COMPLETED,
            PaymentRequestStatus.CANCELLED,
            PaymentRequestStatus.EXPIRED,
        },
        PaymentRequestStatus.COMPLETED: set(),
        PaymentRequestStatus.CANCELLED: set(),
        PaymentRequestStatus.EXPIRED: set(),
    }

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

    @staticmethod
    def _now():
        return timezone.localtime(timezone.now())

    def _get_allowed_next_statuses(self):
        return self.ALLOWED_STATUS_TRANSITIONS.get(self.status, set())

    def _validate_status_transition(self, to_status: str):
        if self.status == to_status:
            return

        allowed_statuses = self._get_allowed_next_statuses()
        if to_status in allowed_statuses:
            return

        raise ValidationError(
            _("Invalid payment request status transition."),
            code="invalid_status_transition",
        )

    def _transition_to(
            self,
            to_status: str,
            *,
            datetime_field: str | None = None,
            extra_updates: dict | None = None,
    ) -> bool:
        self._validate_status_transition(to_status)

        if self.status == to_status:
            return False

        update_fields = ["status"]
        self.status = to_status

        if datetime_field:
            current_value = getattr(self, datetime_field, None)
            if not current_value:
                setattr(self, datetime_field, self._now())
            update_fields.append(datetime_field)

        if extra_updates:
            for field_name, value in extra_updates.items():
                setattr(self, field_name, value)
                if field_name not in update_fields:
                    update_fields.append(field_name)

        self.save(update_fields=update_fields)
        return True

    def mark_awaiting_merchant(
            self,
            *,
            user=None,
            wallet=None,
            merchant_deadline=None,
    ) -> bool:
        extra_updates = {}

        if user is not None:
            extra_updates["paid_by"] = user

        if wallet is not None:
            extra_updates["paid_wallet"] = wallet

        if user is not None or wallet is not None:
            extra_updates["paid_at"] = self.paid_at or self._now()

        if merchant_deadline is not None:
            extra_updates["merchant_confirm_expires_at"] = merchant_deadline
            extra_updates["expires_at"] = merchant_deadline

        return self._transition_to(
            PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION,
            extra_updates=extra_updates or None,
        )

    def mark_completed(
            self,
            *,
            user=None,
            wallet=None,
    ) -> bool:
        extra_updates = {}

        if user is not None:
            extra_updates["paid_by"] = user

        if wallet is not None:
            extra_updates["paid_wallet"] = wallet

        if (
                user is not None
                or wallet is not None
                or self.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        ):
            extra_updates["paid_at"] = self.paid_at or self._now()

        return self._transition_to(
            PaymentRequestStatus.COMPLETED,
            datetime_field="completed_at",
            extra_updates=extra_updates or None,
        )

    def mark_completed_direct(
            self,
            *,
            user=None,
            wallet=None,
    ) -> bool:
        if self.status == PaymentRequestStatus.COMPLETED:
            return False

        if self.status != PaymentRequestStatus.CREATED:
            self._validate_status_transition(PaymentRequestStatus.COMPLETED)

        update_fields = ["status", "completed_at"]

        self.status = PaymentRequestStatus.COMPLETED
        if not self.completed_at:
            self.completed_at = self._now()

        if user is not None:
            self.paid_by = user
            update_fields.append("paid_by")

        if wallet is not None:
            self.paid_wallet = wallet
            update_fields.append("paid_wallet")

        if not self.paid_at:
            self.paid_at = self._now()
            update_fields.append("paid_at")

        self.save(update_fields=update_fields)
        return True

    def mark_cancelled(self) -> bool:
        return self._transition_to(
            PaymentRequestStatus.CANCELLED,
            datetime_field="cancelled_at",
        )

    def mark_expired(self) -> bool:
        return self._transition_to(
            PaymentRequestStatus.EXPIRED,
            datetime_field="expired_at",
        )

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = self._now() + timezone.timedelta(
                minutes=PAYMENT_REQUEST_EXPIRY_MINUTES
            )

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
