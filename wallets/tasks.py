from celery import shared_task
from django.utils import timezone

from wallets.models import PaymentRequest
from wallets.services import rollback_payment, expire_pending_transfer_requests
from wallets.utils.choices import PaymentRequestStatus


def expire_pending_payment_requests():
    now = timezone.now()
    expired = PaymentRequest.objects.filter(
        status__in=[
            PaymentRequestStatus.CREATED,
            PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION,
        ],
        expires_at__lt=now,
    )
    for req in expired:
        req.mark_expired()


def cleanup_cancelled_and_expired_requests():
    for req in PaymentRequest.objects.filter(
            status__in=[
                PaymentRequestStatus.EXPIRED,
                PaymentRequestStatus.CANCELLED,
            ]
    ):
        rollback_payment(req)


@shared_task
def task_expire_pending_payment_requests():
    expire_pending_payment_requests()


@shared_task
def task_cleanup_cancelled_and_expired_requests():
    cleanup_cancelled_and_expired_requests()


@shared_task
def task_expire_pending_transfer_requests():
    expire_pending_transfer_requests()
