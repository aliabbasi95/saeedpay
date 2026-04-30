# apps/wallets/tests/services/test_payment_events.py

import pytest
from rest_framework.exceptions import ValidationError

from apps.wallets.models import PaymentEvent, Wallet
from apps.wallets.services.payment import (
    check_and_expire_payment_request,
    create_payment_request,
    pay_payment_request,
    rollback_payment,
    verify_payment_request,
)
from apps.wallets.utils.choices import (
    OwnerType,
    PaymentEventType,
    PaymentFlowType,
    PaymentRequestStatus,
    TransactionPurpose,
    WalletKind,
)
from apps.wallets.utils.consts import ESCROW_USER_NAME, ESCROW_WALLET_KIND


@pytest.mark.django_db
class TestPaymentEvents:
    def _make_cash_env(self, store, customer_user):
        customer_wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=100_000,
        )
        merchant_wallet = Wallet.objects.create(
            user=store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
            balance=0,
        )
        escrow_wallet = Wallet.objects.get(
            user__username=ESCROW_USER_NAME,
            kind=ESCROW_WALLET_KIND,
        )
        return customer_wallet, merchant_wallet, escrow_wallet

    def test_create_payment_request_creates_event(
        self,
        store,
        customer_user,
    ):
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=25_000,
            return_url="https://example.com/callback",
            external_guid="ORD-EVT-1",
        )

        events = PaymentEvent.objects.filter(payment_request=payment_request).order_by(
            "created_at", "id"
        )

        assert events.count() == 1

        event = events.first()
        assert event.event_type == PaymentEventType.PAYMENT_REQUEST_CREATED
        assert event.payment is None
        assert event.actor == customer_user
        assert event.to_status == PaymentRequestStatus.CREATED
        assert event.extra_data["amount"] == payment_request.amount
        assert event.extra_data["flow_type"] == payment_request.flow_type
        assert event.extra_data["store_id"] == store.id

    def test_create_qr_pos_payment_request_with_merchant_actor_creates_event(
        self,
        store,
        merchant_user,
    ):
        payment_request = create_payment_request(
            store=store,
            customer=None,
            amount=18_000,
            flow_type=PaymentFlowType.QR_POS,
            actor=merchant_user,
        )

        event = (
            PaymentEvent.objects.filter(
                payment_request=payment_request,
                event_type=PaymentEventType.PAYMENT_REQUEST_CREATED,
            )
            .order_by("-created_at", "-id")
            .first()
        )

        assert event is not None
        assert event.actor == merchant_user
        assert event.payment is None
        assert event.to_status == PaymentRequestStatus.CREATED
        assert event.extra_data["flow_type"] == PaymentFlowType.QR_POS
        assert event.extra_data["store_id"] == store.id
        assert event.extra_data["amount"] == payment_request.amount

    def test_online_cash_payment_creates_authorized_and_awaiting_events(
        self,
        store,
        customer_user,
        ensure_escrow,
    ):
        customer_wallet, _, _ = self._make_cash_env(store, customer_user)

        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=12_345,
            return_url="https://example.com/callback",
            external_guid="ORD-EVT-2",
            flow_type=PaymentFlowType.ONLINE,
        )

        payment = pay_payment_request(
            payment_request,
            customer_user,
            customer_wallet,
        )

        events = list(
            PaymentEvent.objects.filter(payment_request=payment_request).order_by(
                "created_at", "id"
            )
        )

        event_types = [event.event_type for event in events]

        assert PaymentEventType.PAYMENT_REQUEST_CREATED in event_types
        assert PaymentEventType.PAYMENT_AUTHORIZED in event_types
        assert PaymentEventType.AWAITING_MERCHANT in event_types

        authorized_event = next(
            event
            for event in events
            if event.event_type == PaymentEventType.PAYMENT_AUTHORIZED
        )
        assert authorized_event.payment_id == payment.id
        assert authorized_event.actor_id == customer_user.id
        assert authorized_event.extra_data["payment_method"] == payment.method
        assert authorized_event.extra_data["flow_type"] == payment.flow_type
        assert authorized_event.extra_data["wallet_id"] == customer_wallet.id

        awaiting_event = next(
            event
            for event in events
            if event.event_type == PaymentEventType.AWAITING_MERCHANT
        )
        assert awaiting_event.payment_id == payment.id
        assert awaiting_event.actor_id == customer_user.id
        assert (
            awaiting_event.to_status
            == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        )
        assert awaiting_event.extra_data["wallet_id"] == customer_wallet.id
        assert awaiting_event.extra_data["merchant_confirm_expires_at"] is not None

    def test_verify_online_cash_payment_creates_verify_settle_and_complete_events(
        self,
        store,
        customer_user,
        ensure_escrow,
    ):
        customer_wallet, merchant_wallet, _ = self._make_cash_env(
            store,
            customer_user,
        )
        merchant_wallet.balance = 0
        merchant_wallet.save(update_fields=["balance"])

        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=40_000,
            return_url="https://example.com/callback",
            external_guid="ORD-EVT-3",
            flow_type=PaymentFlowType.ONLINE,
        )

        payment = pay_payment_request(
            payment_request,
            customer_user,
            customer_wallet,
        )

        verified_payment = verify_payment_request(
            payment_request,
            store=store,
        )

        events = list(
            PaymentEvent.objects.filter(payment_request=payment_request).order_by(
                "created_at", "id"
            )
        )
        event_types = [event.event_type for event in events]

        assert PaymentEventType.PAYMENT_VERIFY_REQUESTED in event_types
        assert PaymentEventType.PAYMENT_SETTLED in event_types
        assert PaymentEventType.PAYMENT_COMPLETED in event_types

        verify_event = next(
            event
            for event in events
            if event.event_type == PaymentEventType.PAYMENT_VERIFY_REQUESTED
        )
        assert verify_event.payment_id == payment.id
        assert verify_event.actor_id == store.merchant.user_id
        assert verify_event.extra_data["store_id"] == store.id

        settled_event = next(
            event
            for event in events
            if event.event_type == PaymentEventType.PAYMENT_SETTLED
        )
        assert settled_event.payment_id == verified_payment.id
        assert settled_event.transaction is not None
        assert settled_event.extra_data["amount"] == verified_payment.amount
        assert (
            settled_event.extra_data["transaction_id"] == settled_event.transaction_id
        )

        completed_event = next(
            event
            for event in events
            if event.event_type == PaymentEventType.PAYMENT_COMPLETED
        )
        assert completed_event.payment_id == verified_payment.id
        assert completed_event.to_status == PaymentRequestStatus.COMPLETED

    def test_expire_created_request_creates_expired_event(
        self,
        store,
        customer_user,
    ):
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=5_000,
            return_url="https://example.com/callback",
            external_guid="ORD-EVT-4",
        )
        payment_request.expires_at = payment_request.expires_at.replace(year=2000)
        payment_request.save(update_fields=["expires_at"])

        with pytest.raises(ValidationError):
            check_and_expire_payment_request(payment_request)

        payment_request.refresh_from_db()
        assert payment_request.status == PaymentRequestStatus.EXPIRED

        expired_event = (
            PaymentEvent.objects.filter(
                payment_request=payment_request,
                event_type=PaymentEventType.PAYMENT_EXPIRED,
            )
            .order_by("-created_at", "-id")
            .first()
        )

        assert expired_event is not None
        assert expired_event.to_status == PaymentRequestStatus.EXPIRED

    def test_expired_cash_payment_rollback_creates_single_rollback_event(
        self,
        store,
        customer_user,
        ensure_escrow,
    ):
        customer_wallet, _, _ = self._make_cash_env(store, customer_user)

        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=7_500,
            return_url="https://example.com/callback",
            external_guid="ORD-EVT-5",
        )

        payment = pay_payment_request(
            payment_request,
            customer_user,
            customer_wallet,
        )
        payment_request.mark_expired()

        rollback_result_first = rollback_payment(payment_request)
        rollback_result_second = rollback_payment(payment_request)

        assert rollback_result_first is not None
        assert rollback_result_second is not None

        rollback_events = PaymentEvent.objects.filter(
            payment_request=payment_request,
            payment=payment,
            event_type=PaymentEventType.PAYMENT_ROLLBACK,
        )

        assert rollback_events.count() == 1

        rollback_event = rollback_events.first()
        assert rollback_event.actor_id == customer_user.id
        assert rollback_event.transaction is not None
        assert rollback_event.transaction.purpose == TransactionPurpose.REVERSAL
        assert rollback_event.extra_data["amount"] == payment.amount
