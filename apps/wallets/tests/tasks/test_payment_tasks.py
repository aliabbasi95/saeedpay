# wallets/tests/tasks/test_payment_tasks.py

import pytest
from django.utils import timezone

from wallets.models import PaymentEvent, Wallet
from wallets.services.payment import pay_payment_request
from wallets.tasks import (
    cleanup_cancelled_and_expired_requests,
    expire_pending_payment_requests,
)
from wallets.utils.choices import (
    OwnerType,
    PaymentEventType,
    PaymentRequestStatus,
    PaymentStatus,
    WalletKind,
)


@pytest.mark.django_db
class TestPaymentTasks:
    def test_expire_created_requests_only_marks_expired(
        self,
        store,
        customer_user,
    ):
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

        expire_event = PaymentEvent.objects.filter(
            payment_request=payment_request_created,
            event_type=PaymentEventType.PAYMENT_EXPIRED,
        ).latest("id")
        assert expire_event.extra_data["reason_code"] == "expired_by_deadline"

    def test_expire_awaiting_request_also_rolls_back_cash_payment_without_extra_cleanup(
        self,
        store,
        customer_user,
        ensure_escrow,
    ):
        from wallets.services.payment import create_payment_request

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

        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=12_345,
            return_url="https://cb.com",
            external_guid="ORD-TASK-CLEANUP-1",
        )
        payment = pay_payment_request(
            payment_request,
            customer_user,
            customer_wallet,
        )

        payment_request.refresh_from_db()
        customer_wallet.refresh_from_db()

        assert (
            payment_request.status
            == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        )
        assert customer_wallet.balance == 50_000 - 12_345

        payment_request.expires_at = timezone.now().replace(year=2000)
        payment_request.save(update_fields=["expires_at"])

        expire_pending_payment_requests()

        payment_request.refresh_from_db()
        payment.refresh_from_db()
        customer_wallet.refresh_from_db()

        assert payment_request.status == PaymentRequestStatus.EXPIRED
        assert payment.status == PaymentStatus.EXPIRED
        assert customer_wallet.balance == 50_000

        rollback_event = PaymentEvent.objects.filter(
            payment_request=payment_request,
            payment=payment,
            event_type=PaymentEventType.PAYMENT_ROLLBACK,
        ).latest("id")
        assert rollback_event.extra_data["reason_code"] == "rollback_after_expire"
        assert rollback_event.extra_data["rollback_type"] == "cash_reversal"

    def test_cleanup_cancelled_and_expired_requests_is_idempotent_after_expire_batch(
        self,
        store,
        customer_user,
        ensure_escrow,
    ):
        from wallets.services.payment import create_payment_request

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

        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=10_000,
            return_url="https://cb.com",
            external_guid="ORD-TASK-CLEANUP-2",
        )
        payment = pay_payment_request(
            payment_request,
            customer_user,
            customer_wallet,
        )

        payment_request.expires_at = timezone.now().replace(year=2000)
        payment_request.save(update_fields=["expires_at"])

        expire_pending_payment_requests()
        cleanup_cancelled_and_expired_requests()

        payment_request.refresh_from_db()
        payment.refresh_from_db()
        customer_wallet.refresh_from_db()

        assert payment_request.status == PaymentRequestStatus.EXPIRED
        assert payment.status == PaymentStatus.EXPIRED
        assert customer_wallet.balance == 50_000
