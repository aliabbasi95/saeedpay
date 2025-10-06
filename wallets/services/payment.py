# wallets/services/payment.py

# wallets/services/payment.py

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from wallets.models import PaymentRequest, Wallet, Transaction
from wallets.utils.choices import (
    PaymentRequestStatus, TransactionStatus, TransactionPurpose, WalletKind,
)
from wallets.utils.consts import (
    ESCROW_WALLET_KIND, ESCROW_USER_NAME,
    MERCHANT_CONFIRM_WINDOW_MINUTES, CREDIT_AUTH_HOLD_EXPIRY_MINUTES,
)

logger = logging.getLogger(__name__)


def create_payment_request(
        store, amount, return_url, customer, description="", external_guid=None
):
    """
    Start at CREATED phase:
    - created_expires_at set (immutable)
    - expires_at mirrors current-phase deadline for compatibility
    """
    created_deadline = timezone.now() + timedelta(
        minutes=CREDIT_AUTH_HOLD_EXPIRY_MINUTES
    )
    return PaymentRequest.objects.create(
        store=store,
        amount=amount,
        customer=customer,
        status=PaymentRequestStatus.CREATED,
        description=description,
        return_url=return_url,
        external_guid=external_guid,
        created_expires_at=created_deadline,
        expires_at=created_deadline,  # compatibility for existing clients
    )


def pay_payment_request(request_obj: PaymentRequest, user, wallet: Wallet):
    """
    CASH: Customer→Escrow (SUCCESS, purpose=ESCROW_DEBIT) + switch to awaiting_merchant
    CREDIT: Create CreditAuthorization (ACTIVE), no wallet move + switch to awaiting_merchant
    On switch, set merchant_confirm_expires_at (immutable) and also update expires_at to current-phase deadline.
    """
    check_and_expire_payment_request(request_obj)

    if request_obj.status != PaymentRequestStatus.CREATED:
        raise ValidationError(
            "پرداخت در این وضعیت قابل انجام نیست.", code="invalid_state"
        )
    if wallet.user_id != user.id:
        raise ValidationError(
            "کیف پول برای کاربر نیست.", code="wallet_not_owned"
        )

    with transaction.atomic():
        if wallet.kind == WalletKind.CASH:
            customer_wallet = Wallet.objects.select_for_update().get(
                pk=wallet.pk
            )
            escrow_wallet = Wallet.objects.select_for_update().get(
                user__username=ESCROW_USER_NAME, kind=ESCROW_WALLET_KIND
            )
            if customer_wallet.available_balance < request_obj.amount:
                raise ValidationError(
                    "موجودی کافی نیست.", code="insufficient_funds"
                )

            customer_wallet.balance -= request_obj.amount
            escrow_wallet.balance += request_obj.amount
            customer_wallet.save(update_fields=["balance"])
            escrow_wallet.save(update_fields=["balance"])

            Transaction.objects.create(
                from_wallet=customer_wallet,
                to_wallet=escrow_wallet,
                amount=request_obj.amount,
                payment_request=request_obj,
                status=TransactionStatus.SUCCESS,
                purpose=TransactionPurpose.ESCROW_DEBIT,
                description="Customer → Escrow",
            )

        elif wallet.kind == WalletKind.CREDIT:
            from credit.models.credit_limit import CreditLimit
            cl = CreditLimit.objects.get_user_credit_limit(user)
            if not cl or not cl.is_active or cl.expiry_date <= timezone.localdate():
                raise ValidationError(
                    "اعتبار فعال یافت نشد یا منقضی شده است.",
                    code="credit_unavailable"
                )
            if int(cl.available_limit) < int(request_obj.amount):
                raise ValidationError(
                    "اعتبار کافی نیست.", code="insufficient_credit"
                )

            from credit.models.authorization import CreditAuthorization as Auth
            existing = Auth.objects.filter(
                payment_request=request_obj, status=Auth.Status.ACTIVE
            ).first()
            if not existing:
                Auth.objects.create(
                    user=user,
                    payment_request=request_obj,
                    amount=int(request_obj.amount),
                    status=Auth.Status.ACTIVE,
                    expires_at=timezone.now() + timedelta(
                        minutes=MERCHANT_CONFIRM_WINDOW_MINUTES
                    ),
                )
        else:
            raise ValidationError(
                "نوع کیف پول مجاز نیست.", code="unsupported_wallet"
            )

        # Switch to merchant confirmation phase; set immutable + mirror expires_at
        m_deadline = timezone.now() + timedelta(
            minutes=MERCHANT_CONFIRM_WINDOW_MINUTES
        )
        request_obj.paid_by = user
        request_obj.paid_wallet = wallet
        request_obj.paid_at = timezone.now()
        request_obj.status = PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        request_obj.merchant_confirm_expires_at = m_deadline
        request_obj.expires_at = m_deadline  # compatibility
        request_obj.save(
            update_fields=[
                "paid_by", "paid_wallet", "paid_at",
                "status", "merchant_confirm_expires_at", "expires_at"
            ]
        )

    return None


def check_and_expire_payment_request(
        payment_request: PaymentRequest, *, raise_exception: bool = True
) -> bool:
    """
    Expire if current-phase deadline (expires_at) has passed. We also set immutable audit fields earlier.
    """
    is_expired = False
    if payment_request.expires_at and payment_request.expires_at < timezone.now():
        if payment_request.status not in [
            PaymentRequestStatus.EXPIRED, PaymentRequestStatus.COMPLETED,
            PaymentRequestStatus.CANCELLED
        ]:
            payment_request.mark_expired()
        is_expired = True
        if raise_exception:
            raise ValidationError(
                detail="درخواست پرداخت منقضی شده است.", code="expired"
            )
    return is_expired


def verify_payment_request(payment_request: PaymentRequest) -> PaymentRequest:
    """
    CASH: Escrow→Merchant (new SUCCESS transaction with purpose=SETTLEMENT)
    CREDIT: settle authorization + add PURCHASE line to CURRENT statement
    """
    # Enforce current phase deadline
    check_and_expire_payment_request(payment_request)

    if payment_request.status != PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION:
        raise ValidationError(
            "پرداخت قابل نهایی‌سازی نیست یا قبلاً تایید شده است.",
            code="invalid_state"
        )

    with transaction.atomic():
        # detect CASH by presence of success ESCROW_DEBIT
        cash_escrow_txn = (
            Transaction.objects.select_for_update()
            .filter(
                payment_request=payment_request,
                status=TransactionStatus.SUCCESS,
                purpose=TransactionPurpose.ESCROW_DEBIT
            )
            .first()
        )

        if cash_escrow_txn:
            escrow_wallet = Wallet.objects.select_for_update().get(
                pk=cash_escrow_txn.to_wallet_id
            )
            merchant_wallet = Wallet.objects.select_for_update().get(
                user=payment_request.store.merchant.user,
                kind="merchant_gateway",
                owner_type="merchant",
            )
            if escrow_wallet.balance < payment_request.amount:
                logger.error(
                    "ESCROW low balance verify: need %s, have %s",
                    payment_request.amount, escrow_wallet.balance
                )
                raise ValidationError(
                    "عملیات با خطا مواجه شد. لطفاً بعداً تلاش کنید.",
                    code="escrow_insufficient"
                )

            escrow_wallet.balance -= payment_request.amount
            merchant_wallet.balance += payment_request.amount
            escrow_wallet.save(update_fields=["balance"])
            merchant_wallet.save(update_fields=["balance"])

            Transaction.objects.create(
                from_wallet=escrow_wallet,
                to_wallet=merchant_wallet,
                amount=payment_request.amount,
                payment_request=payment_request,
                status=TransactionStatus.SUCCESS,
                purpose=TransactionPurpose.SETTLEMENT,
                description="Escrow → Merchant",
            )
        else:
            # CREDIT path
            from credit.models.authorization import CreditAuthorization as Auth
            auth = Auth.objects.select_for_update().filter(
                payment_request=payment_request, status=Auth.Status.ACTIVE
            ).first()
            if auth:
                auth.status = Auth.Status.SETTLED
                auth.save(update_fields=["status"])

                from credit.services.use_cases import StatementUseCases
                StatementUseCases.record_successful_purchase_for_credit(
                    user=payment_request.customer.user,
                    amount=int(payment_request.amount),
                    description=f"Purchase PR {payment_request.reference_code}",
                )
            else:
                if not Auth.objects.filter(
                        payment_request=payment_request,
                        status=Auth.Status.SETTLED
                ).exists():
                    raise ValidationError(
                        "Authorization not found.",
                        code="missing_authorization"
                    )

        payment_request.mark_completed()

    return payment_request


def rollback_payment(payment_request: PaymentRequest) -> None:
    """
    CASH: Escrow→Customer (REVERSAL)
    CREDIT: release ACTIVE authorization (no wallet movement)
    """
    with transaction.atomic():
        cash_escrow_txn = (
            Transaction.objects.select_for_update()
            .filter(
                payment_request=payment_request,
                status=TransactionStatus.SUCCESS,
                purpose=TransactionPurpose.ESCROW_DEBIT
            )
            .first()
        )
        if cash_escrow_txn:
            escrow_wallet = Wallet.objects.select_for_update().get(
                pk=cash_escrow_txn.to_wallet_id
            )
            customer_wallet = Wallet.objects.select_for_update().get(
                pk=cash_escrow_txn.from_wallet_id
            )

            if escrow_wallet.balance < cash_escrow_txn.amount:
                logger.error(
                    "ESCROW low balance rollback: need %s, have %s",
                    cash_escrow_txn.amount, escrow_wallet.balance
                )
                raise ValidationError(
                    "عملیات بازگشت وجه با خطا مواجه شد.",
                    code="escrow_insufficient"
                )

            escrow_wallet.balance -= cash_escrow_txn.amount
            customer_wallet.balance += cash_escrow_txn.amount
            escrow_wallet.save(update_fields=["balance"])
            customer_wallet.save(update_fields=["balance"])

            Transaction.objects.create(
                from_wallet=escrow_wallet,
                to_wallet=customer_wallet,
                amount=cash_escrow_txn.amount,
                payment_request=payment_request,
                status=TransactionStatus.SUCCESS,
                purpose=TransactionPurpose.REVERSAL,
                description="Escrow → Customer (reversal)",
            )
            return

        from credit.models.authorization import CreditAuthorization as Auth
        auth = Auth.objects.select_for_update().filter(
            payment_request=payment_request, status=Auth.Status.ACTIVE
        ).first()
        if auth:
            auth.status = Auth.Status.RELEASED
            auth.save(update_fields=["status"])
