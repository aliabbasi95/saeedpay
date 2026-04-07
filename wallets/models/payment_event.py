# wallets/models/payment_event.py

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from wallets.utils.choices import PaymentEventType


class PaymentEvent(BaseModel):
    payment_request = models.ForeignKey(
        "wallets.PaymentRequest",
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name=_("درخواست پرداخت"),
    )
    payment = models.ForeignKey(
        "wallets.Payment",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name=_("پرداخت"),
    )
    transaction = models.ForeignKey(
        "wallets.Transaction",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payment_events",
        verbose_name=_("تراکنش مرتبط"),
    )
    actor = models.ForeignKey(
        get_user_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payment_events",
        verbose_name=_("کاربر عامل"),
    )
    event_type = models.CharField(
        max_length=64,
        choices=PaymentEventType.choices,
        db_index=True,
        verbose_name=_("نوع رویداد"),
    )
    from_status = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        verbose_name=_("وضعیت قبلی"),
    )
    to_status = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        verbose_name=_("وضعیت جدید"),
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("توضیحات"),
    )
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("داده تکمیلی"),
    )

    @classmethod
    def log(
            cls,
            *,
            payment_request,
            event_type,
            payment=None,
            transaction=None,
            actor=None,
            from_status=None,
            to_status=None,
            description="",
            extra_data=None,
    ):
        return cls.objects.create(
            payment_request=payment_request,
            payment=payment,
            transaction=transaction,
            actor=actor,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            description=description,
            extra_data=extra_data or {},
        )

    class Meta:
        verbose_name = _("رویداد پرداخت")
        verbose_name_plural = _("رویدادهای پرداخت")
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=["payment_request", "event_type"],
                name="payevt_pr_type_idx",
            ),
            models.Index(
                fields=["payment", "event_type"],
                name="payevt_pay_type_idx",
            ),
            models.Index(
                fields=["event_type", "created_at"],
                name="payevt_type_created_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.event_type} | "
            f"PR={self.payment_request_id} | "
            f"PAY={self.payment_id or '-'}"
        )
