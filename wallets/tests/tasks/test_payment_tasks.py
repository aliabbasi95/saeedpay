# wallets/tests/tasks/test_payment_tasks.py

import pytest
from django.utils import timezone

from wallets.models import Wallet
from wallets.services.payment import pay_payment_request
from wallets.tasks import (
    cleanup_cancelled_and_expired_requests,
    expire_pending_payment_requests,
)
from wallets.utils.choices import (
    OwnerType,
    PaymentRequestStatus,
    PaymentStatus,
    WalletKind,
)


@pytest.mark.django_db
class TestPaymentTasks:
    def test_expire_created_requests_only_marks_expired(self, store, customer_user):
        from wallets.services.payment import create_payment_request

        payment_request_created = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=10_000,
            return_url="https://cb.com",
            external_guid="ORD-TASK-EXPIRE-1",
        )
        payment_request_created.expires_at = timezone.now().replace(year=2000)
        payment_request_created.save(update_fields=["expires_at"])

        payment_request_fresh = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=20_000,
            return_url="https://cb.com",
            external_guid="ORD-TASK-EXPIRE-2",
        )

        expire_pending_payment_requests()

        payment_request_created.refresh_from_db()
        payment_request_fresh.refresh_from_db()
        assert payment_request_created.status == PaymentRequestStatus.EXPIRED
        assert payment_request_fresh.status == PaymentRequestStatus.CREATED

    def test_expire_awaiting_then_cleanup_rolls_back_cash_payment(
            self, store, customer_user, ensure_escrow
    ):
        customer_wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=50_000,
        )
        Wallet.objects.create(
            user=store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
            balance=0,
        )

        from wallets.services.payment import create_payment_request

        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=12_345,
            return_url="https://cb.com",
            external_guid="ORD-TASK-CLEANUP-1",
        )
        payment = pay_payment_request(payment_request, customer_user, customer_wallet)
        payment_request.refresh_from_db()
        assert payment_request.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION

        payment_request.expires_at = timezone.now().replace(year=2000)
        payment_request.save(update_fields=["expires_at"])

        expire_pending_payment_requests()
        payment_request.refresh_from_db()
        assert payment_request.status == PaymentRequestStatus.EXPIRED

        cleanup_cancelled_and_expired_requests()

        payment.refresh_from_db()
        customer_wallet.refresh_from_db()
        assert payment.status == PaymentStatus.EXPIRED
        assert customer_wallet.balance == 50_000
