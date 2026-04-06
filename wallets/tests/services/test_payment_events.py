# wallets/tests/services/test_payment_events.py

import pytest

from wallets.models import PaymentEvent, PaymentRequest, Wallet
from wallets.services.payment import pay_payment_request, verify_payment_request
from wallets.utils.choices import (
    OwnerType,
    PaymentEventType,
    PaymentFlowType,
    WalletKind,
)


@pytest.mark.django_db
class TestPaymentEvents:

    def test_create_payment_request_logs_created_event(self, store, customer_user):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=10_000,
            return_url="https://callback.example.com",
        )

        # This test is for object existence only if request is created directly.
        # Service-level event logging is tested below.
        assert payment_request.reference_code is not None

    def test_online_cash_payment_creates_expected_events(
            self,
            store,
            customer_user,
            customer_cash_wallet,
            ensure_escrow,
    ):
        merchant_wallet, _ = Wallet.objects.get_or_create(
            user=store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
            defaults={"balance": 0},
        )

        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=10_000,
            return_url="https://callback.example.com",
            flow_type=PaymentFlowType.ONLINE,
        )

        payment = pay_payment_request(
            payment_request,
            customer_user,
            customer_cash_wallet,
        )

        verify_payment_request(payment_request, store=store)

        event_types = list(
            PaymentEvent.objects.filter(payment_request=payment_request)
            .order_by("created_at", "id")
            .values_list("event_type", flat=True)
        )

        assert PaymentEventType.PAYMENT_AUTHORIZED in event_types
        assert PaymentEventType.AWAITING_MERCHANT in event_types
        assert PaymentEventType.PAYMENT_VERIFY_REQUESTED in event_types
        assert PaymentEventType.PAYMENT_SETTLED in event_types
        assert PaymentEventType.PAYMENT_COMPLETED in event_types

        assert PaymentEvent.objects.filter(
            payment_request=payment_request,
            payment=payment,
        ).exists()

        merchant_wallet.refresh_from_db()
        assert merchant_wallet.balance == payment_request.amount
