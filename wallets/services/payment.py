# wallets/services/payment.py
import uuid

from django.db import transaction
from django.utils import timezone

from wallets.models import PaymentRequest, Wallet, Transaction


def create_payment_request(
        merchant, amount, description="", callback_url=None
):
    # فقط روی کیف "merchant" ایجاد شود
    req = PaymentRequest.objects.create(
        merchant=merchant,
        amount=amount,
        description=description,
        callback_url=callback_url,
        uuid=str(uuid.uuid4())
    )
    return req


def pay_payment_request(request_obj, user, wallet: Wallet):
    if request_obj.is_paid:
        raise Exception("این پرداخت قبلاً انجام شده است.")
    if wallet.user != user:
        raise Exception("کیف پول برای کاربر نیست.")
    if wallet.balance < request_obj.amount:
        raise Exception("موجودی کافی نیست.")

    with transaction.atomic():
        # کسر و واریز
        wallet.balance -= request_obj.amount
        wallet.save()
        # به والت merchant واریز
        merchant_wallet = Wallet.objects.get(
            user=request_obj.merchant, kind='merchant_gateway',
            owner_type='merchant'
        )
        merchant_wallet.balance += request_obj.amount
        merchant_wallet.save()
        # ثبت تراکنش
        Transaction.objects.create(
            from_wallet=wallet,
            to_wallet=merchant_wallet,
            amount=request_obj.amount,
            payment_request=request_obj,
            status="success",
            description=request_obj.description
        )
        request_obj.is_paid = True
        request_obj.paid_by = user
        request_obj.paid_wallet = wallet
        request_obj.paid_at = timezone.now()
        request_obj.save()
    return request_obj
