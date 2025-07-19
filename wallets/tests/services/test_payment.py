# wallets/tests/services/test_payment.py
import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError

from wallets.models import Wallet, Transaction
from wallets.services.payment import (
    create_payment_request, pay_payment_request, verify_payment_request,
    rollback_payment, check_and_expire_payment_request,
)
from wallets.utils.choices import PaymentRequestStatus, TransactionStatus
from wallets.utils.consts import ESCROW_WALLET_KIND, ESCROW_USER_NAME
from wallets.utils.escrow import ensure_escrow_wallet_exists


@pytest.mark.django_db
class TestPaymentService:

    def setup_method(self):
        # پاک‌سازی جدول‌ها بین تست‌ها (اگر لازم بود)
        pass

    def make_customer_and_merchant(self):
        merchant = get_user_model().objects.create(username="merchant_user")
        customer = get_user_model().objects.create(username="customer_user")
        customer_wallet = Wallet.objects.create(
            user=customer, kind="cash", owner_type="customer", balance=50000
        )
        merchant_wallet = Wallet.objects.create(
            user=merchant, kind="merchant_gateway", owner_type="merchant",
            balance=0
        )
        ensure_escrow_wallet_exists()
        escrow_wallet = Wallet.objects.get(
            user__username=ESCROW_USER_NAME, kind=ESCROW_WALLET_KIND
        )
        return merchant, customer, customer_wallet, merchant_wallet, escrow_wallet

    def test_full_payment_flow(self):
        merchant, customer, customer_wallet, merchant_wallet, escrow_wallet = self.make_customer_and_merchant()
        pr = create_payment_request(
            merchant, amount=1234, return_url="https://yourshop.com"
        )
        txn = pay_payment_request(pr, customer, customer_wallet)
        pr.refresh_from_db()
        txn.refresh_from_db()
        escrow_wallet.refresh_from_db()
        assert pr.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        assert txn.status == TransactionStatus.PENDING
        assert escrow_wallet.balance == 1234

        # verify
        verify_payment_request(pr)
        pr.refresh_from_db()
        txn.refresh_from_db()
        merchant_wallet.refresh_from_db()
        assert pr.status == PaymentRequestStatus.COMPLETED
        assert txn.status == TransactionStatus.SUCCESS
        assert merchant_wallet.balance == 1234

        # rollback test
        pr2 = create_payment_request(
            merchant, amount=2000, return_url="https://yourshop.com"
        )
        txn2 = pay_payment_request(pr2, customer, customer_wallet)
        rollback_payment(pr2)
        txn2.refresh_from_db()
        customer_wallet.refresh_from_db()
        assert txn2.status == TransactionStatus.REVERSED
        assert customer_wallet.balance == 50000 - 1234  # قبلی برگشته

    def test_expired_payment_request(self):
        merchant = get_user_model().objects.create(username="merc2")
        pr = create_payment_request(
            merchant, amount=500, return_url="https://ok.com"
        )
        pr.expires_at = pr.expires_at.replace(year=2000)
        pr.save()
        with pytest.raises(Exception):
            check_and_expire_payment_request(pr)
        pr.refresh_from_db()
        assert pr.status == PaymentRequestStatus.EXPIRED

    def test_insufficient_balance(self):
        merchant = get_user_model().objects.create(username="merc3")
        customer = get_user_model().objects.create(username="cust3")
        customer_wallet = Wallet.objects.create(
            user=customer, kind="cash", owner_type="customer", balance=10
        )
        ensure_escrow_wallet_exists()
        pr = create_payment_request(
            merchant, amount=100, return_url="https://ok.com"
        )
        with pytest.raises(Exception):
            pay_payment_request(pr, customer, customer_wallet)

    def test_pay_already_paid_request(self):
        merchant = get_user_model().objects.create(username="merc4")
        customer = get_user_model().objects.create(username="cust4")
        customer_wallet = Wallet.objects.create(
            user=customer, kind="cash", owner_type="customer", balance=1000
        )
        ensure_escrow_wallet_exists()
        pr = create_payment_request(
            merchant, amount=100, return_url="https://ok.com"
        )
        pay_payment_request(pr, customer, customer_wallet)
        pr.status = PaymentRequestStatus.COMPLETED
        pr.save()
        with pytest.raises(Exception):
            pay_payment_request(pr, customer, customer_wallet)

    def test_pay_with_wrong_wallet(self):
        merchant = get_user_model().objects.create(username="merc5")
        customer = get_user_model().objects.create(username="cust5")
        other_user = get_user_model().objects.create(username="other5")
        wrong_wallet = Wallet.objects.create(
            user=other_user, kind="cash", owner_type="customer", balance=5000
        )
        ensure_escrow_wallet_exists()
        pr = create_payment_request(
            merchant, amount=100, return_url="https://ok.com"
        )
        with pytest.raises(Exception):
            pay_payment_request(pr, customer, wrong_wallet)

    def test_verify_wrong_status(self):
        merchant = get_user_model().objects.create(username="merc6")
        pr = create_payment_request(
            merchant, amount=100, return_url="https://ok.com"
        )
        pr.status = PaymentRequestStatus.CREATED
        pr.save()
        with pytest.raises(Exception):
            verify_payment_request(pr)

    def test_double_verify(self):
        merchant, customer, customer_wallet, merchant_wallet, escrow_wallet = self.make_customer_and_merchant()
        pr = create_payment_request(
            merchant, amount=100, return_url="https://ok.com"
        )
        pay_payment_request(pr, customer, customer_wallet)
        verify_payment_request(pr)
        pr.refresh_from_db()

        with pytest.raises(ValidationError) as exc:
            verify_payment_request(pr)

        err = exc.value
        assert isinstance(err.detail, list)
        assert "پرداخت قابل نهایی‌سازی نیست" in err.detail[0]

    def test_double_rollback(self):
        merchant, customer, customer_wallet, merchant_wallet, escrow_wallet = self.make_customer_and_merchant()
        pr = create_payment_request(
            merchant, amount=100, return_url="https://ok.com"
        )
        pay_payment_request(pr, customer, customer_wallet)
        rollback_payment(pr)
        # Second rollback must not fail or double-credit
        rollback_payment(pr)
        customer_wallet.refresh_from_db()
        assert customer_wallet.balance == 50000

    def test_duplicate_payment_on_payment_request(self):
        merchant, customer, customer_wallet, merchant_wallet, escrow_wallet = self.make_customer_and_merchant()
        pr = create_payment_request(
            merchant, amount=100, return_url="https://ok.com"
        )
        pay_payment_request(pr, customer, customer_wallet)
        with pytest.raises(Exception):
            pay_payment_request(pr, customer, customer_wallet)

    def test_description_and_kwargs_on_create(self):
        merchant = get_user_model().objects.create(username="desc_m")
        pr = create_payment_request(
            merchant, amount=777, return_url="https://desc.com",
            description="desc"
        )
        assert pr.description == "desc"

    def test_escrow_wallet_insufficient_balance(self):
        merchant, customer, customer_wallet, merchant_wallet, escrow_wallet = self.make_customer_and_merchant()
        pr = create_payment_request(
            merchant, amount=1000, return_url="https://ok.com"
        )
        txn = pay_payment_request(pr, customer, customer_wallet)
        # Reduce balance in escrow directly!
        escrow_wallet.balance = 0
        escrow_wallet.save()
        with pytest.raises(Exception):
            verify_payment_request(pr)

    def test_verify_on_cancelled_and_expired(self):
        merchant, customer, customer_wallet, merchant_wallet, escrow_wallet = self.make_customer_and_merchant()
        pr = create_payment_request(
            merchant, amount=100, return_url="https://x.com"
        )
        pay_payment_request(pr, customer, customer_wallet)
        pr.status = PaymentRequestStatus.CANCELLED
        pr.save()
        with pytest.raises(Exception):
            verify_payment_request(pr)
        pr.status = PaymentRequestStatus.EXPIRED
        pr.save()
        with pytest.raises(Exception):
            verify_payment_request(pr)

    def test_rollback_on_success_transaction(self):
        merchant, customer, customer_wallet, merchant_wallet, escrow_wallet = self.make_customer_and_merchant()
        pr = create_payment_request(
            merchant, amount=1000, return_url="https://ok.com"
        )
        pay_payment_request(pr, customer, customer_wallet)
        verify_payment_request(pr)  # transaction SUCCESS
        txn = Transaction.objects.filter(payment_request=pr).first()
        merchant_wallet.refresh_from_db()
        old_merchant_balance = merchant_wallet.balance
        rollback_payment(pr)
        txn.refresh_from_db()
        merchant_wallet.refresh_from_db()
        assert txn.status == TransactionStatus.SUCCESS
        assert merchant_wallet.balance == old_merchant_balance

    def test_payment_request_status_on_various_states(self):
        merchant = get_user_model().objects.create(username="kstat")
        pr = create_payment_request(
            merchant, amount=1, return_url="https://stat.com"
        )
        assert pr.status == PaymentRequestStatus.CREATED
        pr.mark_awaiting_merchant()
        assert pr.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        pr.mark_completed()
        assert pr.status == PaymentRequestStatus.COMPLETED
        pr.mark_cancelled()
        assert pr.status == PaymentRequestStatus.CANCELLED
        pr.mark_expired()
        assert pr.status == PaymentRequestStatus.EXPIRED

    def test_create_payment_request_with_description(self):
        merchant = get_user_model().objects.create(username="testdesc")
        pr = create_payment_request(
            merchant, amount=321, return_url="https://desc.com",
            description="a test description"
        )
        assert pr.description == "a test description"
