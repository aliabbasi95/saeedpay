# wallets/tests/tasks/test_payment_tasks.py

import pytest
from django.utils import timezone

from wallets.models import Wallet
from wallets.services.payment import pay_payment_request
from wallets.tasks import (
    expire_pending_payment_requests,
    cleanup_cancelled_and_expired_requests,
)
from wallets.utils.choices import PaymentRequestStatus, WalletKind, OwnerType


@pytest.mark.django_db
class TestPaymentTasks:
    def test_expire_created_requests_only_marks_expired(self, store):
        from wallets.services.payment import create_payment_request
        pr_created = create_payment_request(
            store=store, amount=10_000, return_url="https://cb.com"
        )
        pr_created.expires_at = timezone.now().replace(year=2000)
        pr_created.save(update_fields=["expires_at"])

        pr_fresh = create_payment_request(
            store=store, amount=20_000, return_url="https://cb.com"
        )

        expire_pending_payment_requests()

        pr_created.refresh_from_db()
        pr_fresh.refresh_from_db()
        assert pr_created.status == PaymentRequestStatus.EXPIRED
        assert pr_fresh.status == PaymentRequestStatus.CREATED

    def test_expire_awaiting_then_cleanup_rolls_back_pending_txn(
            self, store, customer_user, ensure_escrow
    ):
        customer_wallet = Wallet.objects.create(
            user=customer_user, kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER, balance=50_000
        )

        from wallets.services.payment import create_payment_request
        pr = create_payment_request(
            store=store, amount=12_345, return_url="https://cb.com"
        )
        pay_payment_request(pr, customer_user, customer_wallet)
        pr.refresh_from_db()
        assert pr.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION

        pr.expires_at = timezone.now().replace(year=2000)
        pr.save(update_fields=["expires_at"])

        expire_pending_payment_requests()
        pr.refresh_from_db()
        assert pr.status == PaymentRequestStatus.EXPIRED

        before = customer_wallet.refresh_from_db() or customer_wallet.balance
        cleanup_cancelled_and_expired_requests()
        customer_wallet.refresh_from_db()

        assert customer_wallet.balance >= before
