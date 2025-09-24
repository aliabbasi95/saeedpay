# wallets/tests/services/test_payment_credit_flow.py

import pytest

from credit.models import Statement
from credit.models.credit_limit import CreditLimit
from wallets.models import Wallet
from wallets.services.payment import (
    create_payment_request,
    pay_payment_request, verify_payment_request,
)
from wallets.utils.choices import OwnerType, WalletKind


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
            self, store, customer_user, ensure_escrow
    ):
        credit_wallet = Wallet.objects.create(
            user=customer_user, kind=WalletKind.CREDIT,
            owner_type=OwnerType.CUSTOMER, balance=0
        )
        self.setup_credit_limit(customer_user, approved=2_000_000)
        pr = create_payment_request(
            store=store, amount=250_000, return_url="https://cb.com"
        )

        txn = pay_payment_request(pr, customer_user, credit_wallet)
        credit_wallet.refresh_from_db()
        assert credit_wallet.balance <= 0
        Wallet.objects.create(
            user=store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
            balance=0
        )
        verify_payment_request(pr)

        st = Statement.objects.get_current_statement(customer_user)
        assert st is not None
        st.refresh_from_db()
        assert st.closing_balance < 0
        assert st.lines.filter(transaction=txn, type="purchase").exists()

    def test_credit_rollback_before_verify_returns_balance(
            self, store, customer_user, ensure_escrow
    ):
        credit_wallet = Wallet.objects.create(
            user=customer_user, kind=WalletKind.CREDIT,
            owner_type=OwnerType.CUSTOMER, balance=0
        )
        self.setup_credit_limit(customer_user, approved=1_000_000)
        pr = create_payment_request(
            store=store, amount=100_000, return_url="https://ok.com"
        )
        from wallets.services.payment import rollback_payment

        pay_payment_request(pr, customer_user, credit_wallet)
        credit_wallet.refresh_from_db()
        bal_after_pay = credit_wallet.balance
        assert bal_after_pay == -100_000

        rollback_payment(pr)
        credit_wallet.refresh_from_db()
        assert credit_wallet.balance == 0
