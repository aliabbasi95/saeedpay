# wallets/tasks.py

from celery import shared_task
from django.utils import timezone

from wallets.models import PaymentRequest
from wallets.services import expire_pending_transfer_requests
from wallets.services.payment import (
    check_and_expire_payment_request,
    rollback_payment,
)
from wallets.utils.choices import PaymentRequestStatus


def expire_pending_payment_requests():
    now = timezone.localtime(timezone.now())
    expired_requests = PaymentRequest.objects.filter(
        status__in=[
            PaymentRequestStatus.CREATED,
            PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION,
        ],
        expires_at__lt=now,
    )
    for payment_request in expired_requests:
        check_and_expire_payment_request(
            payment_request,
            raise_exception=False,
        )


def cleanup_cancelled_and_expired_requests():
    stale_requests = PaymentRequest.objects.filter(
        status__in=[
            PaymentRequestStatus.EXPIRED,
            PaymentRequestStatus.CANCELLED,
        ]
    )
    for payment_request in stale_requests:
        rollback_payment(payment_request)


@shared_task
def task_expire_pending_payment_requests():
    expire_pending_payment_requests()


@shared_task
def task_cleanup_cancelled_and_expired_requests():
    cleanup_cancelled_and_expired_requests()


@shared_task
def task_expire_pending_transfer_requests():
    expire_pending_transfer_requests()
