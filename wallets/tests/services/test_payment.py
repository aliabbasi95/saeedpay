# wallets/tests/services/test_payment.py

import pytest
from rest_framework.exceptions import ValidationError

from wallets.models import Wallet
from wallets.services.payment import (
    create_payment_request, pay_payment_request, verify_payment_request,
    rollback_payment, check_and_expire_payment_request,
)
from wallets.utils.choices import (
    PaymentRequestStatus, TransactionStatus,
    WalletKind, OwnerType,
)
from wallets.utils.consts import ESCROW_WALLET_KIND, ESCROW_USER_NAME


@pytest.mark.django_db
class TestPaymentService:

    def make_env(self, store, customer_user, ensure_escrow):
        customer_wallet = Wallet.objects.create(
            user=customer_user, kind="cash", owner_type="customer",
            balance=50_000
        )
        merchant_wallet = Wallet.objects.create(
            user=store.merchant.user, kind="merchant_gateway",
            owner_type="merchant", balance=0
        )
        escrow_wallet = Wallet.objects.get(
            user__username=ESCROW_USER_NAME, kind=ESCROW_WALLET_KIND
        )
        return customer_wallet, merchant_wallet, escrow_wallet

    def test_full_payment_flow_cash(self, store, customer_user, ensure_escrow):
        customer_wallet, merchant_wallet, escrow_wallet = self.make_env(
            store, customer_user, ensure_escrow
        )
        pr = create_payment_request(
            store=store, amount=1234, return_url="https://yourshop.com"
        )

        txn = pay_payment_request(pr, customer_user, customer_wallet)
        pr.refresh_from_db();
        txn.refresh_from_db();
        escrow_wallet.refresh_from_db()
        assert pr.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        assert txn.status == TransactionStatus.PENDING
        assert escrow_wallet.balance >= 1234

        verify_payment_request(pr)
        pr.refresh_from_db();
        txn.refresh_from_db();
        merchant_wallet.refresh_from_db()
        assert pr.status == PaymentRequestStatus.COMPLETED
        assert txn.status == TransactionStatus.SUCCESS
        assert merchant_wallet.balance >= 1234

        old_balance = merchant_wallet.balance
        rollback_payment(pr)
        merchant_wallet.refresh_from_db()
        assert merchant_wallet.balance == old_balance

    def test_expired_payment_request(self, store):
        pr = create_payment_request(
            store=store, amount=500, return_url="https://ok.com"
        )
        pr.expires_at = pr.expires_at.replace(year=2000)
        pr.save()
        with pytest.raises(ValidationError):
            check_and_expire_payment_request(pr)
        pr.refresh_from_db()
        assert pr.status == PaymentRequestStatus.EXPIRED

    def test_insufficient_balance_cash(
            self, store, customer_user, ensure_escrow
    ):
        wallet = Wallet.objects.create(
            user=customer_user, kind="cash", owner_type="customer", balance=1
        )
        pr = create_payment_request(
            store=store, amount=100, return_url="https://ok.com"
        )
        with pytest.raises(Exception):
            pay_payment_request(pr, customer_user, wallet)

    def test_pay_with_wrong_wallet_owner(
            self, store, customer_user, ensure_escrow
    ):
        from django.contrib.auth import get_user_model
        other = get_user_model().objects.create(username="other")
        wrong_wallet = Wallet.objects.create(
            user=other, kind="cash", owner_type="customer", balance=5_000
        )
        pr = create_payment_request(
            store=store, amount=100, return_url="https://ok.com"
        )
        with pytest.raises(Exception):
            pay_payment_request(pr, customer_user, wrong_wallet)

    def test_verify_wrong_status(self, store):
        pr = create_payment_request(
            store=store, amount=100, return_url="https://ok.com"
        )
        pr.status = PaymentRequestStatus.CREATED
        pr.save()
        with pytest.raises(ValidationError):
            verify_payment_request(pr)

    def test_double_verify(self, store, customer_user, ensure_escrow):
        cust_wallet = Wallet.objects.create(
            user=customer_user, kind="cash", owner_type="customer",
            balance=1_000
        )
        pr = create_payment_request(
            store=store, amount=100, return_url="https://ok.com"
        )
        pay_payment_request(pr, customer_user, cust_wallet)
        Wallet.objects.create(
            user=store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
            balance=0
        )
        verify_payment_request(pr)
        with pytest.raises(ValidationError) as exc:
            verify_payment_request(pr)
        import unicodedata
        msg = unicodedata.normalize("NFKC", str(exc.value))
        assert "پرداخت قابل نهایی" in msg

    def test_double_rollback_is_idempotent(
            self, store, customer_user, ensure_escrow
    ):
        cust_wallet = Wallet.objects.create(
            user=customer_user, kind="cash", owner_type="customer",
            balance=1_000
        )
        pr = create_payment_request(
            store=store, amount=100, return_url="https://ok.com"
        )
        pay_payment_request(pr, customer_user, cust_wallet)
        rollback_payment(pr)
        before = cust_wallet.refresh_from_db() or cust_wallet.balance
        rollback_payment(pr)
        cust_wallet.refresh_from_db()
        assert cust_wallet.balance == before

    def test_escrow_wallet_insufficient_on_verify(
            self, store, customer_user, ensure_escrow
    ):
        cust_wallet = Wallet.objects.create(
            user=customer_user, kind="cash", owner_type="customer",
            balance=10_000
        )
        pr = create_payment_request(
            store=store, amount=1000, return_url="https://ok.com"
        )
        txn = pay_payment_request(pr, customer_user, cust_wallet)
        escrow_wallet = txn.to_wallet
        escrow_wallet.balance = 0
        escrow_wallet.save()
        with pytest.raises(ValidationError):
            verify_payment_request(pr)


@pytest.mark.django_db
class TestPaymentNegativePaths:

    def test_verify_without_merchant_wallet_fails_and_state_unchanged(
            self, store, customer_user, ensure_escrow
    ):
        cust_wallet = Wallet.objects.create(
            user=customer_user, kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER, balance=50_000
        )
        pr = create_payment_request(
            store=store, amount=12_345, return_url="https://cb.com"
        )
        txn = pay_payment_request(pr, customer_user, cust_wallet)

        pr.refresh_from_db()
        assert pr.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        txn.refresh_from_db()
        assert txn.status == TransactionStatus.PENDING

        with pytest.raises(ValidationError):
            verify_payment_request(pr)

        pr.refresh_from_db()
        txn.refresh_from_db()
        assert pr.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        assert txn.status == TransactionStatus.PENDING

    def test_verify_awaiting_but_without_related_transaction(
            self, store
    ):
        pr = create_payment_request(
            store=store, amount=999, return_url="https://ok.com"
        )
        pr.status = PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        pr.save(update_fields=["status"])

        with pytest.raises(ValidationError) as exc:
            verify_payment_request(pr)

        msg = str(exc.value)
        assert "تراکنش مرتبط" in msg
