# apps/wallets/services/payment/payment_rollback_service.py

import logging

from rest_framework.exceptions import ValidationError

from apps.credit.models.authorization import CreditAuthorization
from apps.wallets.models import Payment, Transaction, Wallet
from apps.wallets.services.payment.payment_shared import (
    create_event,
)
from apps.wallets.services.payment.payment_shared import (
    logger as shared_logger,
)
from apps.wallets.utils.choices import (
    PaymentEventType,
    PaymentRequestStatus,
    TransactionPurpose,
)
from saeedpay.logging import log_event

logger = logging.getLogger("saeedpay.wallets.payment")


def rollback_cash_payment(payment: Payment):
    if Transaction.success_exists_for_payment(payment, TransactionPurpose.REVERSAL):
        return Transaction.latest_success_for_payment(
            payment,
            TransactionPurpose.REVERSAL,
        )

    if Transaction.success_exists_for_payment(payment, TransactionPurpose.SETTLEMENT):
        return None

    debit_transaction = Transaction.latest_success_for_payment(
        payment,
        TransactionPurpose.ESCROW_DEBIT,
    )
    if not debit_transaction:
        return None

    escrow_wallet = Wallet.objects.select_for_update().get(
        pk=debit_transaction.to_wallet_id
    )
    customer_wallet = Wallet.objects.select_for_update().get(
        pk=debit_transaction.from_wallet_id
    )

    if escrow_wallet.balance < debit_transaction.amount:
        shared_logger.error(
            "ESCROW low balance rollback: need %s, have %s",
            debit_transaction.amount,
            escrow_wallet.balance,
        )
        log_event(
            logger,
            level="error",
            event="payment_rollback_failed",
            message="Escrow insufficient during rollback.",
            module="wallets.payment",
            action="rollback_cash_payment",
            payment_request_id=payment.payment_request_id,
            payment_request_reference=payment.payment_request.reference_code,
            payment_id=payment.id,
            payment_reference=payment.reference_code,
            amount=debit_transaction.amount,
            payment_method=payment.method,
            reason_code="escrow_insufficient",
        )
        raise ValidationError(
            "عملیات بازگشت وجه با خطا مواجه شد.",
            code="escrow_insufficient",
        )

    escrow_wallet.balance -= debit_transaction.amount
    customer_wallet.balance += debit_transaction.amount
    escrow_wallet.save(update_fields=["balance"])
    customer_wallet.save(update_fields=["balance"])

    reversal = Transaction.create_success(
        payment=payment,
        payment_request=payment.payment_request,
        related_transaction=debit_transaction,
        from_wallet=escrow_wallet,
        to_wallet=customer_wallet,
        amount=debit_transaction.amount,
        purpose=TransactionPurpose.REVERSAL,
        description="Escrow → Customer (reversal)",
    )

    if payment.payment_request.status == PaymentRequestStatus.CANCELLED:
        payment.mark_cancelled()
        reason_code = "rollback_after_cancel"
    elif payment.payment_request.status == PaymentRequestStatus.EXPIRED:
        payment.mark_expired()
        reason_code = "rollback_after_expire"
    else:
        reason_code = "rollback_generic"

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        transaction=reversal,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_ROLLBACK,
        to_status=payment.status,
        description="Cash payment rolled back.",
        extra_data={
            "reason_code": reason_code,
            "rollback_type": "cash_reversal",
            "transaction_id": reversal.id,
            "amount": reversal.amount,
            "payment_status": payment.status,
            "payment_request_status": payment.payment_request.status,
        },
    )

    log_event(
        logger,
        level="info",
        event="payment_rolled_back",
        message="Cash payment rolled back.",
        module="wallets.payment",
        action="rollback_cash_payment",
        payment_request_id=payment.payment_request_id,
        payment_request_reference=payment.payment_request.reference_code,
        payment_id=payment.id,
        payment_reference=payment.reference_code,
        transaction_id=reversal.id,
        amount=reversal.amount,
        payment_method=payment.method,
        payment_status=payment.status,
        reason_code=reason_code,
        rollback_type="cash_reversal",
    )

    return reversal


def rollback_credit_payment(payment: Payment):
    auth = (
        CreditAuthorization.objects.select_for_update()
        .filter(
            payment=payment,
            payment_request=payment.payment_request,
        )
        .order_by("-created_at", "-id")
        .first()
    )
    if not auth:
        return None

    if auth.status == CreditAuthorization.Status.ACTIVE:
        auth.status = CreditAuthorization.Status.RELEASED
        auth.save(update_fields=["status"])

    if payment.payment_request.status == PaymentRequestStatus.CANCELLED:
        payment.mark_cancelled()
        reason_code = "rollback_after_cancel"
    elif payment.payment_request.status == PaymentRequestStatus.EXPIRED:
        payment.mark_expired()
        reason_code = "rollback_after_expire"
    else:
        reason_code = "credit_authorization_released"

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_ROLLBACK,
        to_status=payment.status,
        description="Credit authorization released / rolled back.",
        extra_data={
            "reason_code": reason_code,
            "rollback_type": "credit_release",
            "credit_authorization_id": auth.id,
            "amount": payment.amount,
            "payment_status": payment.status,
            "payment_request_status": payment.payment_request.status,
        },
    )

    log_event(
        logger,
        level="info",
        event="payment_rolled_back",
        message="Credit authorization released / rolled back.",
        module="wallets.payment",
        action="rollback_credit_payment",
        payment_request_id=payment.payment_request_id,
        payment_request_reference=payment.payment_request.reference_code,
        payment_id=payment.id,
        payment_reference=payment.reference_code,
        credit_authorization_id=auth.id,
        amount=payment.amount,
        payment_method=payment.method,
        payment_status=payment.status,
        reason_code=reason_code,
        rollback_type="credit_release",
    )

    return auth
