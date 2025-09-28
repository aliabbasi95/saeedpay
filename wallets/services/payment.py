# wallets/services/payment.py
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from wallets.models import PaymentRequest, Wallet, Transaction
from wallets.utils.choices import PaymentRequestStatus, TransactionStatus
from wallets.utils.consts import ESCROW_WALLET_KIND, ESCROW_USER_NAME

logger = logging.getLogger(__name__)


def create_payment_request(
        store, amount, return_url, customer, description="", external_guid=None
):
    expires_at = timezone.now() + timedelta(minutes=10)
    req = PaymentRequest.objects.create(
        store=store,
        amount=amount,
        customer=customer,
        expires_at=expires_at,
        status=PaymentRequestStatus.CREATED,
        description=description,
        return_url=return_url,
        external_guid=external_guid,
    )
    return req


def pay_payment_request(request_obj, user, wallet: Wallet):
    check_and_expire_payment_request(request_obj)
    if request_obj.status not in [PaymentRequestStatus.CREATED]:
        raise Exception("پرداخت در این وضعیت قابل انجام نیست.")
    if wallet.user != user:
        raise Exception("کیف پول برای کاربر نیست.")
    if request_obj.expires_at and request_obj.expires_at < timezone.now():
        raise Exception("این درخواست منقضی شده است.")

    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
        escrow_wallet = Wallet.objects.select_for_update().get(
            user__username=ESCROW_USER_NAME, kind=ESCROW_WALLET_KIND
        )

        if wallet.kind == "credit":
            from credit.models.credit_limit import CreditLimit
            cl = CreditLimit.objects.get_user_credit_limit(user)
            if not cl or not cl.is_active or cl.expiry_date <= timezone.localdate():
                raise Exception("اعتبار فعال یافت نشد یا منقضی شده است.")
            if int(cl.available_limit) < int(request_obj.amount):
                raise Exception("اعتبار کافی نیست.")
            wallet.balance -= request_obj.amount
            wallet.save(update_fields=["balance"])
        else:
            if wallet.available_balance < request_obj.amount:
                raise Exception("موجودی کافی نیست.")
            wallet.balance -= request_obj.amount
            wallet.save(update_fields=["balance"])

        escrow_wallet.balance += request_obj.amount
        escrow_wallet.save(update_fields=["balance"])

        txn = Transaction.objects.create(
            from_wallet=wallet,
            to_wallet=escrow_wallet,
            amount=request_obj.amount,
            payment_request=request_obj,
            status=TransactionStatus.PENDING,
            description="انتقال به Escrow برای پرداخت"
        )

        request_obj.paid_by = user
        request_obj.paid_wallet = wallet
        request_obj.paid_at = timezone.now()
        request_obj.status = PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        request_obj.save(
            update_fields=["paid_by", "paid_wallet", "paid_at", "status"]
        )

    return txn


def check_and_expire_payment_request(payment_request):
    if payment_request.expires_at and payment_request.expires_at < timezone.now():
        if payment_request.status not in [
            PaymentRequestStatus.EXPIRED, PaymentRequestStatus.COMPLETED,
            PaymentRequestStatus.CANCELLED
        ]:
            payment_request.mark_expired()
        raise ValidationError("درخواست پرداخت منقضی شده است.")


def verify_payment_request(payment_request):
    if payment_request.status != PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION:
        raise ValidationError(
            "پرداخت قابل نهایی‌سازی نیست یا قبلاً تایید شده است."
        )

    with transaction.atomic():
        txn = Transaction.objects.select_for_update().filter(
            payment_request=payment_request, status=TransactionStatus.PENDING
        ).first()
        if not txn:
            raise ValidationError("تراکنش مرتبط با این پرداخت یافت نشد.")

        escrow_wallet = Wallet.objects.select_for_update().get(
            pk=txn.to_wallet_id
        )
        try:
            merchant_wallet = Wallet.objects.select_for_update().get(
                user=payment_request.store.merchant.user,
                kind="merchant_gateway",
                owner_type="merchant"
            )
        except Wallet.DoesNotExist:
            logger.error(
                f"Merchant wallet not found for user {payment_request.store.merchant.user}"
            )
            raise ValidationError(
                "عملیات با خطا مواجه شد. لطفاً بعداً تلاش کنید."
            )

        if escrow_wallet.balance < payment_request.amount:
            logger.error(
                "ESCROW WALLET LOW BALANCE during verify: "
                f"Need {payment_request.amount}, Available {escrow_wallet.balance}"
            )
            raise ValidationError(
                "عملیات با خطا مواجه شد. لطفاً بعداً تلاش کنید."
            )

        escrow_wallet.balance -= payment_request.amount
        merchant_wallet.balance += payment_request.amount
        escrow_wallet.save(update_fields=["balance"])
        merchant_wallet.save(update_fields=["balance"])

        txn.status = TransactionStatus.SUCCESS
        txn.description = ""
        txn.to_wallet = merchant_wallet
        txn.save(update_fields=["status", "description", "to_wallet"])

        if txn.from_wallet.kind == "credit":
            from credit.services.use_cases import StatementUseCases
            StatementUseCases.record_successful_purchase_from_transaction(
                txn.id,
                description=f"Purchase PR {payment_request.reference_code}"
            )

        payment_request.mark_completed()

    return payment_request


def rollback_payment(payment_request):
    txn = Transaction.objects.filter(
        payment_request=payment_request,
        status=TransactionStatus.PENDING
    ).first()
    if not txn:
        return

    escrow_wallet = txn.to_wallet
    customer_wallet = txn.from_wallet

    with transaction.atomic():
        if escrow_wallet.balance < txn.amount:
            logger.error(
                "ESCROW WALLET LOW BALANCE during rollback: "
                f"Need {txn.amount}, Available {escrow_wallet.balance}"
            )
            raise ValidationError("عملیات بازگشت وجه با خطا مواجه شد.")

        escrow_wallet.balance -= txn.amount
        customer_wallet.balance += txn.amount
        escrow_wallet.save()
        customer_wallet.save()

        txn.status = TransactionStatus.REVERSED
        txn.description = "وجه به کیف پول مبدا باگشت داده شد."
        txn.save()
