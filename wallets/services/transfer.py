# wallets/services/transfer.py

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from wallets.models.transfer import WalletTransferRequest
from wallets.models.wallet import Wallet
from wallets.utils.choices import TransferStatus
from utils.reference import generate_reference_code

ALLOWED_SENDER_KINDS = ['cash']
ALLOWED_RECEIVER_KINDS = ['cash']


def create_wallet_transfer_request(
        sender_wallet: Wallet, amount: int, receiver_wallet: Wallet = None,
        receiver_phone: str = None, description: str = '', creator=None
):
    if sender_wallet.kind not in ALLOWED_SENDER_KINDS:
        raise ValidationError("انتقال از این نوع کیف مجاز نیست.")
    if receiver_wallet and receiver_wallet.kind not in ALLOWED_RECEIVER_KINDS:
        raise ValidationError("انتقال به این نوع کیف مجاز نیست.")

    if (
            (
                    receiver_wallet and
                    sender_wallet.user == receiver_wallet.user)
            or
            (
                    receiver_phone and
                    hasattr(sender_wallet.user, "profile") and
                    sender_wallet.user.profile.phone_number == receiver_phone
            )
    ):
        raise ValidationError("انتقال بین کیف‌های یک نفر مجاز نیست.")
    with transaction.atomic():
        sender_wallet = Wallet.objects.select_for_update().get(
            pk=sender_wallet.pk
        )
        if sender_wallet.available_balance < amount:
            raise ValidationError("موجودی قابل رزرو کافی نیست.")

        sender_wallet.reserved_balance += amount
        sender_wallet.save()
        reference_code = generate_reference_code(prefix="WT", random_digits=6)

        transfer = WalletTransferRequest.objects.create(
            sender_wallet=sender_wallet,
            receiver_wallet=receiver_wallet,
            receiver_phone_number=receiver_phone,
            amount=amount,
            reference_code=reference_code,
            description=description,
            status=TransferStatus.SUCCESS if receiver_wallet else TransferStatus.PENDING_CONFIRMATION,
            creator=creator
        )

        if receiver_wallet:
            if sender_wallet.reserved_balance < amount or sender_wallet.balance < amount:
                raise ValidationError("موجودی کافی نیست.")
            sender_wallet.reserved_balance -= amount
            sender_wallet.balance -= amount
            sender_wallet.save()
            receiver_wallet = Wallet.objects.select_for_update().get(
                pk=receiver_wallet.pk
            )
            receiver_wallet.balance += amount
            receiver_wallet.save()
            from wallets.models.transaction import Transaction
            txn = Transaction.objects.create(
                from_wallet=sender_wallet,
                to_wallet=receiver_wallet,
                amount=amount,
                status="success",
                description="انتقال مستقیم کیف به کیف"
            )
            transfer.transaction = txn
            transfer.status = TransferStatus.SUCCESS
            transfer.save()
    return transfer


def check_and_expire_transfer_request(transfer_request):
    if transfer_request.expires_at and transfer_request.expires_at < timezone.localtime(
            timezone.now()
            ):
        if transfer_request.status == TransferStatus.PENDING_CONFIRMATION:
            transfer_request.status = TransferStatus.EXPIRED
            transfer_request.save()
            sender_wallet = transfer_request.sender_wallet
            sender_wallet.balance += transfer_request.amount
            sender_wallet.save()
        raise ValidationError("درخواست انتقال منقضی شده است.")


def confirm_wallet_transfer_request(
        transfer: WalletTransferRequest, receiver_wallet: Wallet, user
):
    with transaction.atomic():
        if receiver_wallet.user != user:
            raise ValidationError("کیف پول مقصد متعلق به شما نیست.")
        if transfer.receiver_phone_number and hasattr(
                user, "profile"
        ) and user.profile.phone_number != transfer.receiver_phone_number:
            raise ValidationError("شما مجاز به تایید این انتقال نیستید.")
        if transfer.status != TransferStatus.PENDING_CONFIRMATION:
            raise ValidationError(
                "این انتقال قابل تایید نیست یا قبلاً تایید شده است."
            )
        sender_wallet = Wallet.objects.select_for_update().get(
            pk=transfer.sender_wallet.pk
        )
        if sender_wallet.reserved_balance < transfer.amount:
            raise ValidationError("موجودی رزروشده کافی نیست.")
        if sender_wallet.balance < transfer.amount:
            raise ValidationError("موجودی کیف پول کافی نیست.")

        sender_wallet.reserved_balance -= transfer.amount
        sender_wallet.balance -= transfer.amount
        sender_wallet.save()

        receiver_wallet = Wallet.objects.select_for_update().get(
            pk=receiver_wallet.pk
        )
        receiver_wallet.balance += transfer.amount
        receiver_wallet.save()

        from wallets.models.transaction import Transaction
        txn = Transaction.objects.create(
            from_wallet=sender_wallet,
            to_wallet=receiver_wallet,
            amount=transfer.amount,
            status="success",
            description="انتقال تاییدشده با شماره موبایل"
        )

        transfer.receiver_wallet = receiver_wallet
        transfer.transaction = txn
        transfer.status = TransferStatus.SUCCESS
        transfer.save()

    return transfer


def reject_wallet_transfer_request(transfer: WalletTransferRequest):
    from django.db import transaction
    with transaction.atomic():
        sender_wallet = Wallet.objects.select_for_update().get(
            pk=transfer.sender_wallet.pk
        )
        if sender_wallet.reserved_balance < transfer.amount:
            raise ValidationError("موجودی رزروشده برای آزادسازی کافی نیست.")
        sender_wallet.reserved_balance -= transfer.amount
        sender_wallet.save()

        transfer.status = TransferStatus.REJECTED
        transfer.save()
    return transfer


def expire_pending_transfer_requests():
    now = timezone.localtime(timezone.now())
    expired = WalletTransferRequest.objects.filter(
        status=TransferStatus.PENDING_CONFIRMATION,
        expires_at__lt=now,
    )
    for req in expired:
        with transaction.atomic():
            sender_wallet = Wallet.objects.select_for_update().get(
                pk=req.sender_wallet.pk
            )
            if sender_wallet.reserved_balance >= req.amount:
                sender_wallet.reserved_balance -= req.amount
                sender_wallet.save()
            req.status = TransferStatus.EXPIRED
            req.save()
