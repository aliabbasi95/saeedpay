# apps/wallets/tasks/payment.py

from celery import shared_task

from apps.wallets.services.payment import (
    cleanup_cancelled_and_expired_requests_batch,
    expire_pending_payment_requests_batch,
)


def expire_pending_payment_requests():
    expire_pending_payment_requests_batch()


def cleanup_cancelled_and_expired_requests():
    cleanup_cancelled_and_expired_requests_batch()


@shared_task
def task_expire_pending_payment_requests():
    expire_pending_payment_requests()


@shared_task
def task_cleanup_cancelled_and_expired_requests():
    cleanup_cancelled_and_expired_requests()
