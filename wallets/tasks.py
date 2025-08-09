# wallets/tasks.py

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from wallets.models import InstallmentRequest
from wallets.models import PaymentRequest
from wallets.services import evaluate_user_credit
from wallets.services import rollback_payment, expire_pending_transfer_requests
from wallets.utils.choices import InstallmentRequestStatus
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


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_underwriting_for_request(self, request_id: int):
    try:
        with transaction.atomic():
            req = InstallmentRequest.objects.select_for_update().get(
                id=request_id
            )

            if req.status not in {
                InstallmentRequestStatus.UNDERWRITING,
                InstallmentRequestStatus.CREATED
            }:
                return

            base_amount = req.user_requested_amount or req.store_proposed_amount

            approved = evaluate_user_credit(base_amount, req.contract)
            req.mark_validated(approved_amount=approved)
    except InstallmentRequest.DoesNotExist:
        return
    except Exception as exc:
        raise self.retry(exc=exc)
