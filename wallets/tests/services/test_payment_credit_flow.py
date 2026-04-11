# wallets/tests/services/test_payment_credit_flow.py

import pytest

from credit.models import CreditAuthorization, Statement
from credit.models.credit_limit import CreditLimit
from wallets.models import Wallet
from wallets.services.payment import (
    create_payment_request,
    pay_payment_request,
    rollback_payment,
    verify_payment_request,
)
from wallets.utils.choices import (
    OwnerType,
    PaymentFlowType,
    PaymentRequestStatus,
    PaymentStatus,
    WalletKind,
)


@pytest.mark.django_db
class TestPaymentCreditFlow:

    def setup_credit_limit(self, customer_user, approved=1_000_000):
        from django.utils import timezone

        limit = CreditLimit.objects.create(
            user=customer_user,
            approved_limit=approved,
            is_active=True,
            expiry_date=timezone.localdate().replace(
                year=timezone.localdate().year + 1
            ),
        )
        limit.activate()
        return limit

    def test_credit_purchase_records_statement_after_verify(
            self, store, customer_user
    ):
        credit_wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CREDIT,
            owner_type=OwnerType.CUSTOMER,
            balance=0,
        )
        self.setup_credit_limit(customer_user, approved=2_000_000)

        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=250_000,
            return_url="https://cb.com",
            external_guid="ORD-CREDIT-VERIFY-1",
        )

        payment = pay_payment_request(payment_request, customer_user, credit_wallet)
        payment.refresh_from_db()
        payment_request.refresh_from_db()

        assert payment.status == PaymentStatus.AWAITING_MERCHANT_CONFIRMATION
        assert payment_request.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION

        auth = CreditAuthorization.objects.get(payment=payment)
        assert auth.status == CreditAuthorization.Status.ACTIVE

        verify_payment_request(payment_request, store=store)

        statement = Statement.objects.get_current_statement(customer_user)
        assert statement is not None
        statement.refresh_from_db()
        assert statement.closing_balance < 0
        assert statement.lines.filter(payment=payment, type="purchase").exists()

        auth.refresh_from_db()
        assert auth.status == CreditAuthorization.Status.SETTLED

    def test_credit_rollback_before_verify_releases_authorization(
            self, store, customer_user
    ):
        credit_wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CREDIT,
            owner_type=OwnerType.CUSTOMER,
            balance=0,
        )
        self.setup_credit_limit(customer_user, approved=1_000_000)

        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=100_000,
            return_url="https://ok.com",
            external_guid="ORD-CREDIT-ROLLBACK-1",
        )

        payment = pay_payment_request(payment_request, customer_user, credit_wallet)
        auth = CreditAuthorization.objects.get(payment=payment)
        assert auth.status == CreditAuthorization.Status.ACTIVE

        payment_request.mark_expired()
        rollback_payment(payment_request)

        auth.refresh_from_db()
        payment.refresh_from_db()
        assert auth.status == CreditAuthorization.Status.RELEASED
        assert payment.status == PaymentStatus.EXPIRED

    def test_qr_credit_purchase_is_finalized_immediately(
            self, store, customer_user
    ):
        credit_wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CREDIT,
            owner_type=OwnerType.CUSTOMER,
            balance=0,
        )
        self.setup_credit_limit(customer_user, approved=1_000_000)

        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=150_000,
            flow_type=PaymentFlowType.QR_POS,
            actor=store.merchant.user,
        )

        payment = pay_payment_request(payment_request, customer_user, credit_wallet)
        payment_request.refresh_from_db()
        payment.refresh_from_db()

        assert payment_request.status == PaymentRequestStatus.COMPLETED
        assert payment.status == PaymentStatus.COMPLETED

        auth = CreditAuthorization.objects.get(payment=payment)
        assert auth.status == CreditAuthorization.Status.SETTLED

        statement = Statement.objects.get_current_statement(customer_user)
        assert statement.lines.filter(payment=payment, type="purchase").exists()
