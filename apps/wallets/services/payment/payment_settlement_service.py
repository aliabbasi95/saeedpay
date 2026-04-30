# apps/wallets/services/payment/payment_settlement_service.py

import logging

from rest_framework.exceptions import ValidationError

from apps.credit.models.authorization import CreditAuthorization
from apps.credit.models.statement import Statement
from apps.credit.models.statement_line import StatementLine
from apps.credit.utils.choices import StatementLineType
from apps.wallets.models import Payment, Transaction, Wallet
from apps.wallets.services.payment.payment_shared import (
    create_event,
    get_merchant_gateway_wallet,
)
from apps.wallets.services.payment.payment_shared import (
    logger as shared_logger,
)
from apps.wallets.utils.choices import (
    PaymentEventType,
    TransactionPurpose,
)
from saeedpay.logging import log_event

logger = logging.getLogger("saeedpay.wallets.payment")


def settle_cash_payment(payment: Payment):
    customer_to_escrow_txn = Transaction.latest_success_for_payment(
        payment,
        TransactionPurpose.ESCROW_DEBIT,
    )
    if not customer_to_escrow_txn:
        raise ValidationError(
            "تراکنش انتقال به امانی برای این پرداخت پیدا نشد.",
            code="missing_escrow_transaction",
        )

    escrow_wallet = Wallet.objects.select_for_update().get(
        pk=customer_to_escrow_txn.to_wallet_id
    )
    merchant_wallet = get_merchant_gateway_wallet(payment)

    if escrow_wallet.balance < payment.amount:
        shared_logger.error(
            "ESCROW low balance verify: need %s, have %s",
            payment.amount,
            escrow_wallet.balance,
        )
        log_event(
            logger,
            level="error",
            event="payment_settlement_failed",
            message="Escrow insufficient during cash settlement.",
            module="wallets.payment",
            action="settle_cash_payment",
            payment_request_id=payment.payment_request_id,
            payment_request_reference=payment.payment_request.reference_code,
            payment_id=payment.id,
            payment_reference=payment.reference_code,
            amount=payment.amount,
            payment_method=payment.method,
            reason_code="escrow_insufficient",
        )
        raise ValidationError(
            "عملیات با خطا مواجه شد. لطفاً بعداً تلاش کنید.",
            code="escrow_insufficient",
        )

    escrow_wallet.balance -= payment.amount
    merchant_wallet.balance += payment.amount
    escrow_wallet.save(update_fields=["balance"])
    merchant_wallet.save(update_fields=["balance"])

    settlement_txn = Transaction.create_success(
        payment=payment,
        payment_request=payment.payment_request,
        from_wallet=escrow_wallet,
        to_wallet=merchant_wallet,
        amount=payment.amount,
        purpose=TransactionPurpose.SETTLEMENT,
        description="Escrow → Merchant",
        related_transaction=customer_to_escrow_txn,
    )

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        transaction=settlement_txn,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_SETTLED,
        description="Cash payment settled from escrow to merchant.",
        extra_data={
            "transaction_id": settlement_txn.id,
            "amount": payment.amount,
        },
    )

    log_event(
        logger,
        level="info",
        event="payment_settled",
        message="Cash payment settled.",
        module="wallets.payment",
        action="settle_cash_payment",
        payment_request_id=payment.payment_request_id,
        payment_request_reference=payment.payment_request.reference_code,
        payment_id=payment.id,
        payment_reference=payment.reference_code,
        transaction_id=settlement_txn.id,
        amount=payment.amount,
        payment_method=payment.method,
    )

    return settlement_txn


def settle_credit_payment(payment: Payment):
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
        raise ValidationError(
            "Authorization not found.",
            code="missing_authorization",
        )

    if auth.status == CreditAuthorization.Status.SETTLED:
        return auth

    if auth.status != CreditAuthorization.Status.ACTIVE:
        raise ValidationError(
            "Authorization is not active.",
            code="invalid_authorization_state",
        )

    auth.status = CreditAuthorization.Status.SETTLED
    auth.save(update_fields=["status"])

    statement, _ = Statement.objects.get_or_create_current_statement(payment.payer)
    existing_line = StatementLine.all_objects.filter(
        payment=payment,
        type=StatementLineType.PURCHASE,
    ).first()
    if existing_line:
        return auth

    StatementLine.objects.create(
        statement=statement,
        type=StatementLineType.PURCHASE,
        amount=payment.amount,
        payment=payment,
        payment_request=payment.payment_request,
        description=f"Purchase {payment.payment_request.reference_code}",
    )

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_SETTLED,
        description="Credit payment settled.",
        extra_data={
            "credit_authorization_id": auth.id,
            "amount": payment.amount,
        },
    )

    log_event(
        logger,
        level="info",
        event="payment_settled",
        message="Credit payment settled.",
        module="wallets.payment",
        action="settle_credit_payment",
        payment_request_id=payment.payment_request_id,
        payment_request_reference=payment.payment_request.reference_code,
        payment_id=payment.id,
        payment_reference=payment.reference_code,
        credit_authorization_id=auth.id,
        amount=payment.amount,
        payment_method=payment.method,
    )

    return auth
