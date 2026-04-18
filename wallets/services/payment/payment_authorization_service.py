# wallets/services/payment/payment_authorization_service.py

import logging

from rest_framework.exceptions import ValidationError

from credit.models.authorization import CreditAuthorization
from saeedpay.logging import log_event
from wallets.models import Payment, Transaction, Wallet
from wallets.services.payment.payment_shared import (
    build_authorized_event_extra,
    create_event,
    credit_auth_hold_expiry,
    get_escrow_wallet,
)
from wallets.utils.choices import (
    PaymentEventType,
    TransactionPurpose,
)

logger = logging.getLogger("saeedpay.wallets.payment")


def authorize_cash_payment(payment: Payment, customer_wallet: Wallet):
    escrow_wallet = get_escrow_wallet()

    if customer_wallet.available_balance < payment.amount:
        raise ValidationError(
            "موجودی کافی نیست.",
            code="insufficient_funds",
        )

    customer_wallet.balance -= payment.amount
    escrow_wallet.balance += payment.amount
    customer_wallet.save(update_fields=["balance"])
    escrow_wallet.save(update_fields=["balance"])

    escrow_transaction = Transaction.create_success(
        payment=payment,
        payment_request=payment.payment_request,
        from_wallet=customer_wallet,
        to_wallet=escrow_wallet,
        amount=payment.amount,
        purpose=TransactionPurpose.ESCROW_DEBIT,
        description="Customer → Escrow",
    )

    payment.mark_authorized()

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        transaction=escrow_transaction,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_AUTHORIZED,
        to_status=payment.status,
        description="Cash payment authorized.",
        extra_data=build_authorized_event_extra(
            payment=payment,
            wallet_id=customer_wallet.id,
        ),
    )

    log_event(
        logger,
        level="info",
        event="payment_authorized",
        message="Cash payment authorized.",
        module="wallets.payment",
        action="authorize_cash_payment",
        payment_request_id=payment.payment_request_id,
        payment_request_reference=payment.payment_request.reference_code,
        payment_id=payment.id,
        payment_reference=payment.reference_code,
        user_id=getattr(payment.payer, "id", None),
        amount=payment.amount,
        payment_method=payment.method,
        payment_status=payment.status,
        transaction_id=escrow_transaction.id,
    )


def authorize_credit_payment(payment: Payment):
    from credit.models.credit_limit import CreditLimit

    credit_limit = CreditLimit.objects.get_user_credit_limit(payment.payer)
    if not credit_limit or not credit_limit.is_active:
        raise ValidationError(
            "اعتبار فعال یافت نشد یا منقضی شده است.",
            code="credit_unavailable",
        )
    if int(credit_limit.available_limit) < int(payment.amount):
        raise ValidationError(
            "اعتبار کافی نیست.",
            code="insufficient_credit",
        )

    authorization_expires_at = credit_auth_hold_expiry()

    authorization = CreditAuthorization.objects.create(
        user=payment.payer,
        payment=payment,
        payment_request=payment.payment_request,
        amount=int(payment.amount),
        status=CreditAuthorization.Status.ACTIVE,
        expires_at=authorization_expires_at,
    )

    payment.authorization_expires_at = authorization_expires_at
    payment.mark_authorized()

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_AUTHORIZED,
        to_status=payment.status,
        description="Credit payment authorized.",
        extra_data=build_authorized_event_extra(
            payment=payment,
            wallet_id=payment.payer_wallet_id,
            extra={"credit_authorization_id": authorization.id},
        ),
    )

    log_event(
        logger,
        level="info",
        event="payment_authorized",
        message="Credit payment authorized.",
        module="wallets.payment",
        action="authorize_credit_payment",
        payment_request_id=payment.payment_request_id,
        payment_request_reference=payment.payment_request.reference_code,
        payment_id=payment.id,
        payment_reference=payment.reference_code,
        user_id=getattr(payment.payer, "id", None),
        amount=payment.amount,
        payment_method=payment.method,
        payment_status=payment.status,
        credit_authorization_id=authorization.id,
    )
