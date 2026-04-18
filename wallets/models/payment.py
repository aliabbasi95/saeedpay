# wallets/models/payment.py

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from utils.reference import generate_reference_code
from wallets.models.wallet import Wallet
from wallets.utils.choices import PaymentFlowType, PaymentMethod, PaymentStatus


class Payment(BaseModel):
    ALLOWED_STATUS_TRANSITIONS = {
        PaymentStatus.CREATED: {
            PaymentStatus.AUTHORIZED,
            PaymentStatus.FAILED,
            PaymentStatus.CANCELLED,
            PaymentStatus.EXPIRED,
        },
        PaymentStatus.AUTHORIZED: {
            PaymentStatus.AWAITING_MERCHANT_CONFIRMATION,
            PaymentStatus.COMPLETED,
            PaymentStatus.FAILED,
            PaymentStatus.CANCELLED,
            PaymentStatus.EXPIRED,
        },
        PaymentStatus.AWAITING_MERCHANT_CONFIRMATION: {
            PaymentStatus.COMPLETED,
            PaymentStatus.FAILED,
            PaymentStatus.CANCELLED,
            PaymentStatus.EXPIRED,
        },
        PaymentStatus.COMPLETED: set(),
        PaymentStatus.CANCELLED: set(),
        PaymentStatus.EXPIRED: set(),
        PaymentStatus.FAILED: set(),
    }

    FINAL_STATUSES = {
        PaymentStatus.COMPLETED,
        PaymentStatus.CANCELLED,
        PaymentStatus.EXPIRED,
        PaymentStatus.FAILED,
    }

    ACTIVE_STATUSES = {
        PaymentStatus.CREATED,
        PaymentStatus.AUTHORIZED,
        PaymentStatus.AWAITING_MERCHANT_CONFIRMATION,
    }

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

    @staticmethod
    def _now():
        return timezone.localtime(timezone.now())

    @property
    def is_final(self) -> bool:
        return self.status in self.FINAL_STATUSES

    def _get_allowed_next_statuses(self):
        return self.ALLOWED_STATUS_TRANSITIONS.get(self.status, set())

    def can_transition_to(self, to_status: str) -> bool:
        if self.status == to_status:
            return True
        return to_status in self._get_allowed_next_statuses()

    def _validate_status_transition(self, to_status: str):
        if self.status == to_status:
            return

        if self.status == PaymentStatus.COMPLETED:
            raise ValidationError(
                _("This payment has already been completed."),
                code="already_completed",
            )

        if to_status in self._get_allowed_next_statuses():
            return

        raise ValidationError(
            _("Invalid payment status transition."),
            code="invalid_status_transition",
        )

    def _transition_to(
            self,
            to_status: str,
            *,
            datetime_field: str | None = None,
            failure_reason: str | None = None,
            extra_update_fields: list[str] | None = None,
    ):
        self._validate_status_transition(to_status)

        if self.status == to_status:
            return

        update_fields = ["status"]

        self.status = to_status

        if datetime_field:
            if not getattr(self, datetime_field):
                setattr(self, datetime_field, self._now())
            update_fields.append(datetime_field)

        if failure_reason is not None:
            self.failure_reason = failure_reason
            update_fields.append("failure_reason")

        if extra_update_fields:
            update_fields.extend(extra_update_fields)

        update_fields = list(dict.fromkeys(update_fields))
        self.save(update_fields=update_fields)

    def mark_authorized(self):
        self._transition_to(PaymentStatus.AUTHORIZED)

    def mark_awaiting_merchant(self):
        self._transition_to(PaymentStatus.AWAITING_MERCHANT_CONFIRMATION)

    def mark_completed(self):
        self._transition_to(
            PaymentStatus.COMPLETED,
            datetime_field="completed_at",
        )

    def mark_failed(self, reason: str = ""):
        self._transition_to(
            PaymentStatus.FAILED,
            failure_reason=reason,
        )

    def mark_cancelled(self):
        self._transition_to(
            PaymentStatus.CANCELLED,
            datetime_field="cancelled_at",
        )

    def mark_expired(self):
        self._transition_to(
            PaymentStatus.EXPIRED,
            datetime_field="expired_at",
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
        constraints = [
            models.UniqueConstraint(
                fields=["payment_request"],
                condition=models.Q(
                    status__in=[
                        PaymentStatus.CREATED,
                        PaymentStatus.AUTHORIZED,
                        PaymentStatus.AWAITING_MERCHANT_CONFIRMATION,
                    ]
                ),
                name="uniq_active_payment_per_request",
            ),
        ]
