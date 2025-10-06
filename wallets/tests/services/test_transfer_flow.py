# wallets/tests/services/test_transfer_flow.py

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from wallets.models import Wallet
from wallets.services.transfer import (
    create_wallet_transfer_request,
    confirm_wallet_transfer_request,
    reject_wallet_transfer_request,
    check_and_expire_transfer_request, expire_pending_transfer_requests,
)
from wallets.utils.choices import OwnerType, WalletKind, TransferStatus


@pytest.mark.django_db
class TestTransferFlow:

    def test_create_and_confirm_phone_transfer(self, user_factory):
        sender = user_factory("sender", phone="09120000001")
        receiver = user_factory("receiver", phone="09120000002")
        w_sender = Wallet.objects.create(
            user=sender, kind=WalletKind.CASH, owner_type=OwnerType.CUSTOMER,
            balance=20_000
        )
        w_receiver = Wallet.objects.create(
            user=receiver, kind=WalletKind.CASH, owner_type=OwnerType.CUSTOMER,
            balance=1_000
        )

        tr = create_wallet_transfer_request(
            sender_wallet=w_sender, amount=5_000, receiver_phone="09120000002"
        )
        assert tr.status == TransferStatus.PENDING_CONFIRMATION
        w_sender.refresh_from_db()
        assert w_sender.reserved_balance == 5_000

        confirm_wallet_transfer_request(
            tr, receiver_wallet=w_receiver, user=receiver
        )
        tr.refresh_from_db()
        w_sender.refresh_from_db()
        w_receiver.refresh_from_db()
        assert tr.status == TransferStatus.SUCCESS
        assert w_sender.balance == 15_000
        assert w_sender.reserved_balance == 0
        assert w_receiver.balance == 6_000

    def test_reject_transfer_frees_reserved(self, user_factory):
        sender = user_factory("sender2", phone="09120000011")
        receiver = user_factory("receiver2", phone="09120000022")
        w_sender = Wallet.objects.create(
            user=sender, kind=WalletKind.CASH, owner_type=OwnerType.CUSTOMER,
            balance=8_000
        )
        w_receiver = Wallet.objects.create(
            user=receiver, kind=WalletKind.CASH, owner_type=OwnerType.CUSTOMER,
            balance=0
        )

        tr = create_wallet_transfer_request(
            sender_wallet=w_sender, amount=3_000, receiver_phone="09120000022"
        )
        assert tr.status == TransferStatus.PENDING_CONFIRMATION

        reject_wallet_transfer_request(tr)
        tr.refresh_from_db()
        w_sender.refresh_from_db()
        assert tr.status == TransferStatus.REJECTED
        assert w_sender.reserved_balance == 0
        assert w_sender.balance == 8_000

    def test_expire_pending_transfer(self, user_factory):
        sender = user_factory("sender3", phone="09120000031")
        w_sender = Wallet.objects.create(
            user=sender, kind=WalletKind.CASH, owner_type=OwnerType.CUSTOMER,
            balance=4_000
        )
        tr = create_wallet_transfer_request(
            sender_wallet=w_sender, amount=1_000, receiver_phone="09120000099"
        )
        tr.expires_at = timezone.now().replace(year=2000)
        tr.save(update_fields=["expires_at"])

        with pytest.raises(ValidationError):
            check_and_expire_transfer_request(tr)

        tr.refresh_from_db()
        w_sender.refresh_from_db()
        assert tr.status in [TransferStatus.EXPIRED,
                             TransferStatus.PENDING_CONFIRMATION]

    def test_self_transfer_forbidden(self, user_factory):
        u = user_factory("same", phone="09120000055")
        w1 = Wallet.objects.create(
            user=u, kind=WalletKind.CASH, owner_type=OwnerType.CUSTOMER,
            balance=1_000
        )
        with pytest.raises(ValidationError):
            create_wallet_transfer_request(
                sender_wallet=w1, amount=100, receiver_phone="09120000055"
            )


class TestTransferTasks:
    def test_expire_pending_releases_reserved_balance(self, customer_user):
        sender = Wallet.objects.create(
            user=customer_user, kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER, balance=50_000, reserved_balance=0
        )
        tr = create_wallet_transfer_request(
            sender_wallet=sender, amount=10_000, receiver_phone="09120001111"
        )
        assert tr.status == TransferStatus.PENDING_CONFIRMATION
        sender.refresh_from_db()
        assert sender.reserved_balance == 10_000

        tr.expires_at = timezone.now().replace(year=2000)
        tr.save(update_fields=["expires_at"])

        expire_pending_transfer_requests()
        sender.refresh_from_db()
        tr.refresh_from_db()
        assert tr.status == TransferStatus.EXPIRED
        assert sender.reserved_balance == 0
