# wallets/services/payment/payment_batch_service.py

import logging

from saeedpay.logging import log_event
from wallets.models import PaymentRequest
from wallets.services.payment.payment_processing_service import rollback_payment
from wallets.services.payment.payment_request_service import expire_payment_request
from wallets.services.payment.payment_shared import now_local
from wallets.utils.choices import PaymentRequestStatus

logger = logging.getLogger("saeedpay.wallets.payment")


def expire_pending_payment_requests_batch():
    now = now_local()

    expired_request_ids = list(
        PaymentRequest.objects.filter(
            status__in=[
                PaymentRequestStatus.CREATED,
                PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION,
            ],
            expires_at__isnull=False,
            expires_at__lt=now,
        ).values_list("id", flat=True)
    )

    log_event(
        logger,
        level="info",
        event="payment_expiry_batch_started",
        message="Payment expiry batch started.",
        module="wallets.payment",
        action="expire_pending_payment_requests_batch",
        count=len(expired_request_ids),
    )

    for payment_request_id in expired_request_ids:
        expire_payment_request(PaymentRequest(id=payment_request_id))

    log_event(
        logger,
        level="info",
        event="payment_expiry_batch_finished",
        message="Payment expiry batch finished.",
        module="wallets.payment",
        action="expire_pending_payment_requests_batch",
        count=len(expired_request_ids),
    )


def cleanup_cancelled_and_expired_requests_batch():
    """
    Legacy safety-net cleanup.

    Expiration/cancellation services already invoke rollback_payment()
    as part of the state transition flow. This batch remains intentionally
    idempotent as a fallback cleanup for stale records that may exist from
    older flows or interrupted processes.
    """
    stale_request_ids = list(
        PaymentRequest.objects.filter(
            status__in=[
                PaymentRequestStatus.EXPIRED,
                PaymentRequestStatus.CANCELLED,
            ]
        ).values_list("id", flat=True)
    )

    log_event(
        logger,
        level="info",
        event="payment_cleanup_batch_started",
        message="Payment cleanup batch started.",
        module="wallets.payment",
        action="cleanup_cancelled_and_expired_requests_batch",
        count=len(stale_request_ids),
    )

    for payment_request_id in stale_request_ids:
        rollback_payment(PaymentRequest(id=payment_request_id))

    log_event(
        logger,
        level="info",
        event="payment_cleanup_batch_finished",
        message="Payment cleanup batch finished.",
        module="wallets.payment",
        action="cleanup_cancelled_and_expired_requests_batch",
        count=len(stale_request_ids),
    )
