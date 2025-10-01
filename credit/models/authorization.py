# credit/models/authorization.py

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from utils.reference import generate_reference_code


class CreditAuthorization(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "active", _("فعال")
        SETTLED = "settled", _("نهایی‌شده")
        RELEASED = "released", _("آزادشده")
        EXPIRED = "expired", _("منقضی")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="credit_authorizations",
        verbose_name=_("کاربر")
    )
    payment_request = models.ForeignKey(
        "wallets.PaymentRequest", on_delete=models.CASCADE,
        related_name="credit_authorizations",
        verbose_name=_("درخواست پرداخت")
    )
    amount = models.BigIntegerField(verbose_name=_("مبلغ"))
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE,
        db_index=True
    )
    expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("انقضا")
    )
    reference_code = models.CharField(
        max_length=20, unique=True, null=True, blank=True,
        verbose_name=_("کد پیگیری")
    )

    def save(self, *args, **kwargs):
        if not self.reference_code:
            for _ in range(5):
                code = generate_reference_code(prefix="AUTH", random_digits=6)
                if not CreditAuthorization.objects.filter(
                        reference_code=code
                ).exists():
                    self.reference_code = code
                    break
            else:
                raise Exception(
                    "Failed to generate authorization reference code."
                )
        super().save(*args, **kwargs)

    def is_active(self) -> bool:
        if self.status != self.Status.ACTIVE:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        return True

    class Meta:
        verbose_name = _("هولد اعتباری")
        verbose_name_plural = _("هولدهای اعتباری")
        constraints = [
            # One ACTIVE auth per PR (hard guard for idempotency)
            models.UniqueConstraint(
                fields=["payment_request"],
                condition=models.Q(status="active"),
                name="uniq_active_auth_per_payment_request",
            ),
            models.CheckConstraint(
                name="auth_amount_gt_zero", check=models.Q(amount__gt=0)
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "status"], name="auth_user_status_idx"
            ),
            models.Index(fields=["expires_at"], name="auth_expires_idx"),
        ]
