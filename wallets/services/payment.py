# wallets/services/payment.py

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from credit.models.authorization import CreditAuthorization
from credit.models.statement import Statement
from credit.models.statement_line import StatementLine
from credit.utils.choices import StatementLineType
from wallets.models import Payment, PaymentRequest, Transaction, Wallet
from wallets.utils.choices import (
    OwnerType,
    PaymentFlowType,
    PaymentMethod,
    PaymentRequestStatus,
    PaymentStatus,
    TransactionPurpose,
    TransactionStatus,
    WalletKind,
)
from wallets.utils.consts import (
    CREDIT_AUTH_HOLD_EXPIRY_MINUTES,
    ESCROW_USER_NAME,
    ESCROW_WALLET_KIND,
    MERCHANT_CONFIRM_WINDOW_MINUTES,
)

logger = logging.getLogger(__name__)


def create_payment_request(
        store,
        amount,
        return_url,
        customer=None,
        description="",
        external_guid=None,
        flow_type=PaymentFlowType.ONLINE,
):
    created_deadline = timezone.localtime(timezone.now()) + timedelta(
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
        flow_type=flow_type,
        created_expires_at=created_deadline,
        expires_at=created_deadline,
    )


def list_eligible_wallets_for_payment_request(user, payment_request):
    wallets = Wallet.objects.filter(
        user=user,
        owner_type=OwnerType.CUSTOMER,
    ).order_by("kind")

    eligible_ids = []

    for wallet in wallets:
        if wallet.kind == WalletKind.CASH:
            if int(wallet.available_balance or 0) >= int(payment_request.amount):
                eligible_ids.append(wallet.id)
        elif wallet.kind == WalletKind.CREDIT:
            from credit.models.credit_limit import CreditLimit

            credit_limit = CreditLimit.objects.get_user_credit_limit(user)
            if (
                    credit_limit
                    and getattr(credit_limit, "is_active", False)
                    and getattr(credit_limit, "available_limit", 0) >= int(
                payment_request.amount
            )
            ):
                eligible_ids.append(wallet.id)

    return wallets.filter(id__in=eligible_ids)


def check_and_expire_payment_request(
        payment_request: PaymentRequest,
        *,
        raise_exception: bool = True,
) -> bool:
    payment_request = PaymentRequest.objects.get(pk=payment_request.pk)

    if (
            payment_request.expires_at
            and payment_request.expires_at < timezone.localtime(timezone.now())
    ):
        if payment_request.status not in [
            PaymentRequestStatus.EXPIRED,
            PaymentRequestStatus.COMPLETED,
            PaymentRequestStatus.CANCELLED,
        ]:
            expire_payment_request(payment_request)

        if raise_exception:
            raise ValidationError(
                detail="درخواست پرداخت منقضی شده است.",
                code="expired",
            )
        return True

    return False


def expire_payment_request(payment_request: PaymentRequest):
    with transaction.atomic():
        request_obj = PaymentRequest.objects.select_for_update().get(
            pk=payment_request.pk
        )
        if request_obj.status in [
            PaymentRequestStatus.EXPIRED,
            PaymentRequestStatus.CANCELLED,
            PaymentRequestStatus.COMPLETED,
        ]:
            return request_obj

        request_obj.mark_expired()
        return request_obj


def cancel_payment_request(payment_request: PaymentRequest):
    with transaction.atomic():
        request_obj = PaymentRequest.objects.select_for_update().get(
            pk=payment_request.pk
        )
        if request_obj.status in [
            PaymentRequestStatus.CANCELLED,
            PaymentRequestStatus.EXPIRED,
            PaymentRequestStatus.COMPLETED,
        ]:
            return request_obj

        request_obj.mark_cancelled()
        return request_obj


def pay_payment_request(request_obj: PaymentRequest, user, wallet: Wallet):
    with transaction.atomic():
        payment_request = (
            PaymentRequest.objects.select_for_update()
            .select_related("store__merchant__user", "customer__user")
            .get(pk=request_obj.pk)
        )

        check_and_expire_payment_request(payment_request)

        if payment_request.status != PaymentRequestStatus.CREATED:
            raise ValidationError(
                "پرداخت در این وضعیت قابل انجام نیست.",
                code="invalid_state",
            )

        customer_wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
        if customer_wallet.user_id != user.id:
            raise ValidationError(
                "کیف پول برای کاربر نیست.",
                code="wallet_not_owned",
            )

        existing_payment = (
            Payment.objects.select_for_update()
            .filter(
                payment_request=payment_request,
                status__in=[
                    PaymentStatus.CREATED,
                    PaymentStatus.AUTHORIZED,
                    PaymentStatus.AWAITING_MERCHANT_CONFIRMATION,
                    PaymentStatus.COMPLETED,
                ],
            )
            .order_by("-created_at")
            .first()
        )
        if existing_payment:
            raise ValidationError(
                "این درخواست پرداخت قبلاً پردازش شده است.",
                code="already_processed",
            )

        if customer_wallet.kind == WalletKind.CASH:
            payment_method = PaymentMethod.CASH
        elif customer_wallet.kind == WalletKind.CREDIT:
            payment_method = PaymentMethod.CREDIT
        else:
            raise ValidationError(
                "نوع کیف پول مجاز نیست.",
                code="unsupported_wallet",
            )

        payment = Payment.objects.create(
            payment_request=payment_request,
            payer=user,
            payer_wallet=customer_wallet,
            amount=payment_request.amount,
            method=payment_method,
            flow_type=payment_request.flow_type,
            status=PaymentStatus.CREATED,
        )

        if payment.method == PaymentMethod.CASH:
            _authorize_cash_payment(payment, customer_wallet)
            if payment.flow_type == PaymentFlowType.QR_POS:
                _settle_cash_payment(payment)
                _mark_payment_completed(payment)
                _mark_request_completed(payment_request, user, customer_wallet)
            else:
                _mark_payment_awaiting_merchant(payment)
                _mark_request_awaiting_merchant(
                    payment_request,
                    user,
                    customer_wallet,
                    payment.merchant_confirm_expires_at,
                )

        elif payment.method == PaymentMethod.CREDIT:
            _authorize_credit_payment(payment)
            if payment.flow_type == PaymentFlowType.QR_POS:
                _settle_credit_payment(payment)
                _mark_payment_completed(payment)
                _mark_request_completed(payment_request, user, customer_wallet)
            else:
                _mark_payment_awaiting_merchant(payment)
                _mark_request_awaiting_merchant(
                    payment_request,
                    user,
                    customer_wallet,
                    payment.merchant_confirm_expires_at,
                )

        return payment


def verify_payment_request(payment_request: PaymentRequest, *, store=None) -> Payment:
    with transaction.atomic():
        request_obj = (
            PaymentRequest.objects.select_for_update()
            .select_related("store__merchant__user")
            .get(pk=payment_request.pk)
        )

        check_and_expire_payment_request(request_obj)

        if store is not None and request_obj.store_id != store.id:
            raise ValidationError(
                "این درخواست پرداخت متعلق به این فروشگاه نیست.",
                code="forbidden_store",
            )

        if request_obj.status != PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION:
            raise ValidationError(
                "پرداخت قابل نهایی‌سازی نیست یا قبلاً تایید شده است.",
                code="invalid_state",
            )

        payment = (
            Payment.objects.select_for_update()
            .filter(
                payment_request=request_obj,
                status=PaymentStatus.AWAITING_MERCHANT_CONFIRMATION,
            )
            .order_by("-created_at")
            .first()
        )
        if not payment:
            raise ValidationError(
                "پرداخت مرتبط برای نهایی‌سازی پیدا نشد.",
                code="missing_payment",
            )

        if payment.method == PaymentMethod.CASH:
            _settle_cash_payment(payment)
        elif payment.method == PaymentMethod.CREDIT:
            _settle_credit_payment(payment)
        else:
            raise ValidationError(
                "روش پرداخت پشتیبانی نمی‌شود.",
                code="unsupported_payment_method",
            )

        _mark_payment_completed(payment)
        _mark_request_completed(
            request_obj,
            request_obj.paid_by,
            request_obj.paid_wallet,
        )
        return payment


def rollback_payment(payment_request: PaymentRequest):
    with transaction.atomic():
        request_obj = PaymentRequest.objects.select_for_update().get(
            pk=payment_request.pk
        )

        payment = (
            Payment.objects.select_for_update()
            .filter(payment_request=request_obj)
            .order_by("-created_at")
            .first()
        )
        if not payment:
            return None

        if payment.status == PaymentStatus.COMPLETED:
            return None

        if payment.method == PaymentMethod.CASH:
            return _rollback_cash_payment(payment)

        if payment.method == PaymentMethod.CREDIT:
            return _rollback_credit_payment(payment)

        return None


def _authorize_cash_payment(payment: Payment, customer_wallet: Wallet):
    escrow_wallet = Wallet.objects.select_for_update().get(
        user__username=ESCROW_USER_NAME,
        kind=ESCROW_WALLET_KIND,
    )

    if customer_wallet.available_balance < payment.amount:
        raise ValidationError(
            "موجودی کافی نیست.",
            code="insufficient_funds",
        )

    customer_wallet.balance -= payment.amount
    escrow_wallet.balance += payment.amount
    customer_wallet.save(update_fields=["balance"])
    escrow_wallet.save(update_fields=["balance"])

    Transaction.objects.create(
        payment=payment,
        payment_request=payment.payment_request,
        from_wallet=customer_wallet,
        to_wallet=escrow_wallet,
        amount=payment.amount,
        status=TransactionStatus.SUCCESS,
        purpose=TransactionPurpose.ESCROW_DEBIT,
        description="Customer → Escrow",
    )

    payment.status = PaymentStatus.AUTHORIZED
    payment.save(update_fields=["status"])


def _authorize_credit_payment(payment: Payment):
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

    authorization_expires_at = timezone.localtime(timezone.now()) + timedelta(
        minutes=CREDIT_AUTH_HOLD_EXPIRY_MINUTES
    )

    CreditAuthorization.objects.create(
        user=payment.payer,
        payment=payment,
        payment_request=payment.payment_request,
        amount=int(payment.amount),
        status=CreditAuthorization.Status.ACTIVE,
        expires_at=authorization_expires_at,
    )

    payment.status = PaymentStatus.AUTHORIZED
    payment.authorization_expires_at = authorization_expires_at
    payment.save(update_fields=["status", "authorization_expires_at"])


def _mark_payment_awaiting_merchant(payment: Payment):
    merchant_deadline = timezone.localtime(timezone.now()) + timedelta(
        minutes=MERCHANT_CONFIRM_WINDOW_MINUTES
    )
    payment.status = PaymentStatus.AWAITING_MERCHANT_CONFIRMATION
    payment.merchant_confirm_expires_at = merchant_deadline
    payment.save(update_fields=["status", "merchant_confirm_expires_at"])


def _mark_request_awaiting_merchant(
        payment_request: PaymentRequest,
        user,
        wallet,
        merchant_deadline,
):
    payment_request.paid_by = user
    payment_request.paid_wallet = wallet
    payment_request.paid_at = timezone.localtime(timezone.now())
    payment_request.status = PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
    payment_request.merchant_confirm_expires_at = merchant_deadline
    payment_request.expires_at = merchant_deadline
    payment_request.save(
        update_fields=[
            "paid_by",
            "paid_wallet",
            "paid_at",
            "status",
            "merchant_confirm_expires_at",
            "expires_at",
        ]
    )


def _mark_payment_completed(payment: Payment):
    if payment.status == PaymentStatus.COMPLETED:
        return
    payment.status = PaymentStatus.COMPLETED
    payment.completed_at = timezone.localtime(timezone.now())
    payment.save(update_fields=["status", "completed_at"])


def _mark_request_completed(payment_request: PaymentRequest, user, wallet):
    payment_request.paid_by = user
    payment_request.paid_wallet = wallet
    if not payment_request.paid_at:
        payment_request.paid_at = timezone.localtime(timezone.now())
    payment_request.status = PaymentRequestStatus.COMPLETED
    payment_request.completed_at = timezone.localtime(timezone.now())
    payment_request.save(
        update_fields=[
            "paid_by",
            "paid_wallet",
            "paid_at",
            "status",
            "completed_at",
        ]
    )


def _settle_cash_payment(payment):
    customer_to_escrow_txn = payment.transactions.filter(
        status=TransactionStatus.SUCCESS,
        purpose=TransactionPurpose.ESCROW_DEBIT,
    ).first()

    if not customer_to_escrow_txn:
        raise ValidationError(
            "تراکنش انتقال به امانی برای این پرداخت پیدا نشد.",
            code="missing_escrow_transaction",
        )

    escrow_wallet = Wallet.objects.select_for_update().get(
        pk=customer_to_escrow_txn.to_wallet_id
    )

    try:
        merchant_wallet = Wallet.objects.select_for_update().get(
            user=payment.payment_request.store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
        )
    except Wallet.DoesNotExist:
        raise ValidationError(
            "کیف پول فروشگاه برای تسویه یافت نشد.",
            code="merchant_wallet_not_found",
        )

    if escrow_wallet.balance < payment.amount:
        logger.error(
            "ESCROW low balance verify: need %s, have %s",
            payment.amount,
            escrow_wallet.balance,
        )
        raise ValidationError(
            "عملیات با خطا مواجه شد. لطفاً بعداً تلاش کنید.",
            code="escrow_insufficient",
        )

    escrow_wallet.balance -= payment.amount
    merchant_wallet.balance += payment.amount
    escrow_wallet.save(update_fields=["balance"])
    merchant_wallet.save(update_fields=["balance"])

    settlement_txn = Transaction.objects.create(
        payment=payment,
        payment_request=payment.payment_request,
        from_wallet=escrow_wallet,
        to_wallet=merchant_wallet,
        amount=payment.amount,
        status=TransactionStatus.SUCCESS,
        purpose=TransactionPurpose.SETTLEMENT,
        description="Escrow → Merchant",
        related_transaction=customer_to_escrow_txn,
    )
    return settlement_txn


def _settle_credit_payment(payment: Payment):
    auth = (
        CreditAuthorization.objects.select_for_update()
        .filter(
            payment=payment,
            payment_request=payment.payment_request,
        )
        .order_by("-created_at")
        .first()
    )
    if not auth:
        raise ValidationError(
            "Authorization not found.",
            code="missing_authorization",
        )

    if auth.status == CreditAuthorization.Status.SETTLED:
        return

    if auth.status != CreditAuthorization.Status.ACTIVE:
        raise ValidationError(
            "Authorization is not active.",
            code="invalid_authorization_state",
        )

    auth.status = CreditAuthorization.Status.SETTLED
    auth.save(update_fields=["status"])

    statement, _ = Statement.objects.get_or_create_current_statement(
        payment.payer
    )
    existing_line = StatementLine.all_objects.filter(
        payment=payment,
        type=StatementLineType.PURCHASE,
    ).first()
    if existing_line:
        return

    StatementLine.objects.create(
        statement=statement,
        type=StatementLineType.PURCHASE,
        amount=payment.amount,
        payment=payment,
        payment_request=payment.payment_request,
        description=f"Purchase {payment.payment_request.reference_code}",
    )


def _rollback_cash_payment(payment: Payment):
    reversal_exists = payment.transactions.filter(
        purpose=TransactionPurpose.REVERSAL,
        status=TransactionStatus.SUCCESS,
    ).exists()
    if reversal_exists:
        return payment.transactions.filter(
            purpose=TransactionPurpose.REVERSAL,
            status=TransactionStatus.SUCCESS,
        ).order_by("-created_at").first()

    settlement_exists = payment.transactions.filter(
        purpose=TransactionPurpose.SETTLEMENT,
        status=TransactionStatus.SUCCESS,
    ).exists()
    if settlement_exists:
        return None

    debit_transaction = payment.transactions.filter(
        purpose=TransactionPurpose.ESCROW_DEBIT,
        status=TransactionStatus.SUCCESS,
    ).order_by("-created_at").first()
    if not debit_transaction:
        return None

    escrow_wallet = Wallet.objects.select_for_update().get(
        pk=debit_transaction.to_wallet_id
    )
    customer_wallet = Wallet.objects.select_for_update().get(
        pk=debit_transaction.from_wallet_id
    )

    if escrow_wallet.balance < debit_transaction.amount:
        logger.error(
            "ESCROW low balance rollback: need %s, have %s",
            debit_transaction.amount,
            escrow_wallet.balance,
        )
        raise ValidationError(
            "عملیات بازگشت وجه با خطا مواجه شد.",
            code="escrow_insufficient",
        )

    escrow_wallet.balance -= debit_transaction.amount
    customer_wallet.balance += debit_transaction.amount
    escrow_wallet.save(update_fields=["balance"])
    customer_wallet.save(update_fields=["balance"])

    reversal = Transaction.objects.create(
        payment=payment,
        payment_request=payment.payment_request,
        related_transaction=debit_transaction,
        from_wallet=escrow_wallet,
        to_wallet=customer_wallet,
        amount=debit_transaction.amount,
        status=TransactionStatus.SUCCESS,
        purpose=TransactionPurpose.REVERSAL,
        description="Escrow → Customer (reversal)",
    )

    if payment.payment_request.status == PaymentRequestStatus.CANCELLED:
        payment.status = PaymentStatus.CANCELLED
        payment.cancelled_at = timezone.localtime(timezone.now())
        payment.save(update_fields=["status", "cancelled_at"])
    elif payment.payment_request.status == PaymentRequestStatus.EXPIRED:
        payment.status = PaymentStatus.EXPIRED
        payment.expired_at = timezone.localtime(timezone.now())
        payment.save(update_fields=["status", "expired_at"])

    return reversal


def _rollback_credit_payment(payment: Payment):
    auth = (
        CreditAuthorization.objects.select_for_update()
        .filter(
            payment=payment,
            payment_request=payment.payment_request,
        )
        .order_by("-created_at")
        .first()
    )
    if not auth:
        return None

    if auth.status == CreditAuthorization.Status.ACTIVE:
        auth.status = CreditAuthorization.Status.RELEASED
        auth.save(update_fields=["status"])

    if payment.payment_request.status == PaymentRequestStatus.CANCELLED:
        payment.status = PaymentStatus.CANCELLED
        payment.cancelled_at = timezone.localtime(timezone.now())
        payment.save(update_fields=["status", "cancelled_at"])
    elif payment.payment_request.status == PaymentRequestStatus.EXPIRED:
        payment.status = PaymentStatus.EXPIRED
        payment.expired_at = timezone.localtime(timezone.now())
        payment.save(update_fields=["status", "expired_at"])

    return auth
