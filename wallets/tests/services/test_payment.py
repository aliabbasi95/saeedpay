# wallets/tests/services/test_payment.py

import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError

from customers.models import Customer
from wallets.models import Wallet, PaymentRequest
from wallets.services.payment import (
    check_and_expire_payment_request,
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
    TransactionPurpose,
    TransactionStatus,
    WalletKind,
)
from wallets.utils.consts import ESCROW_USER_NAME, ESCROW_WALLET_KIND


@pytest.mark.django_db
class TestPaymentService:

    def make_env(self, store, customer_user, ensure_escrow):
        customer_wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=50_000,
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

    def test_full_payment_flow_cash(self, store, customer_user, ensure_escrow):
        customer_wallet, merchant_wallet, escrow_wallet = self.make_env(
            store, customer_user, ensure_escrow
        )
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=1234,
            return_url="https://yourshop.com",
            external_guid="ORD-1234",
        )

        payment = pay_payment_request(payment_request, customer_user, customer_wallet)
        payment_request.refresh_from_db()
        payment.refresh_from_db()
        escrow_wallet.refresh_from_db()

        assert payment_request.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        assert payment.status == PaymentStatus.AWAITING_MERCHANT_CONFIRMATION
        assert escrow_wallet.balance >= 1234

        debit = payment.transactions.get(purpose=TransactionPurpose.ESCROW_DEBIT)
        assert debit.status == TransactionStatus.SUCCESS

        verified_payment = verify_payment_request(payment_request, store=store)
        payment_request.refresh_from_db()
        verified_payment.refresh_from_db()
        merchant_wallet.refresh_from_db()

        assert payment_request.status == PaymentRequestStatus.COMPLETED
        assert verified_payment.status == PaymentStatus.COMPLETED
        assert merchant_wallet.balance >= 1234

        settlement = verified_payment.transactions.get(
            purpose=TransactionPurpose.SETTLEMENT
        )
        assert settlement.status == TransactionStatus.SUCCESS

        old_balance = merchant_wallet.balance
        rollback_payment(payment_request)
        merchant_wallet.refresh_from_db()
        assert merchant_wallet.balance == old_balance

    def test_qr_cash_payment_is_finalized_immediately(
            self, store, customer_user, ensure_escrow
    ):
        customer_wallet, merchant_wallet, _ = self.make_env(
            store, customer_user, ensure_escrow
        )
        payment_request = create_payment_request(
            store=store,
            customer=None,
            amount=2000,
            flow_type=PaymentFlowType.QR_POS,
            actor=store.merchant.user,
        )

        payment = pay_payment_request(payment_request, customer_user, customer_wallet)
        payment_request.refresh_from_db()
        payment.refresh_from_db()
        merchant_wallet.refresh_from_db()

        assert payment_request.status == PaymentRequestStatus.COMPLETED
        assert payment.status == PaymentStatus.COMPLETED
        assert payment_request.paid_by == customer_user
        assert payment_request.paid_wallet == customer_wallet
        assert payment.transactions.filter(
            purpose=TransactionPurpose.ESCROW_DEBIT
        ).exists()
        assert payment.transactions.filter(
            purpose=TransactionPurpose.SETTLEMENT
        ).exists()
        assert merchant_wallet.balance >= 2000

    def test_online_payment_without_return_url_fails(
            self, store, customer_user
    ):
        with pytest.raises(ValidationError) as exc:
            create_payment_request(
                store=store,
                customer=customer_user.customer,
                amount=1000,
                return_url=None,
                external_guid="ORD-1",
                flow_type=PaymentFlowType.ONLINE,
            )

        assert exc.value.get_codes()[0] == "return_url_required"

    def test_online_payment_without_external_guid_fails(
            self, store, customer_user
    ):
        with pytest.raises(ValidationError) as exc:
            create_payment_request(
                store=store,
                customer=customer_user.customer,
                amount=1000,
                return_url="https://cb.com",
                external_guid=None,
                flow_type=PaymentFlowType.ONLINE,
            )

        assert exc.value.get_codes()[0] == "external_guid_required"

    def test_qr_payment_with_return_url_fails(
            self, store
    ):
        with pytest.raises(ValidationError) as exc:
            create_payment_request(
                store=store,
                customer=None,
                amount=1000,
                return_url="https://cb.com",
                flow_type=PaymentFlowType.QR_POS,
                actor=store.merchant.user,
            )

        assert exc.value.get_codes()[0] == "return_url_not_allowed"

    def test_qr_payment_with_external_guid_fails(
            self, store
    ):
        with pytest.raises(ValidationError) as exc:
            create_payment_request(
                store=store,
                customer=None,
                amount=1000,
                external_guid="POS-1",
                flow_type=PaymentFlowType.QR_POS,
                actor=store.merchant.user,
            )

        assert exc.value.get_codes()[0] == "external_guid_not_allowed"

    def test_bound_request_cannot_be_paid_by_other_customer(
            self, store, customer_user, ensure_escrow, user_factory
    ):
        other_user = user_factory("other_customer_for_service")
        Customer.objects.get_or_create(user=other_user)

        other_wallet = Wallet.objects.create(
            user=other_user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=50_000,
        )

        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=100,
            return_url="https://ok.com",
            external_guid="ORD-BOUND-1",
        )

        with pytest.raises(ValidationError) as exc:
            pay_payment_request(payment_request, other_user, other_wallet)

        assert exc.value.get_codes()[0] == "payment_request_not_allowed"

    def test_expired_payment_request(self, store, customer_user):
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=500,
            return_url="https://ok.com",
            external_guid="ORD-EXP-1",
        )
        payment_request.expires_at = payment_request.expires_at.replace(year=2000)
        payment_request.save(update_fields=["expires_at"])

        with pytest.raises(ValidationError):
            check_and_expire_payment_request(payment_request)

        payment_request.refresh_from_db()
        assert payment_request.status == PaymentRequestStatus.EXPIRED

    def test_insufficient_balance_cash(self, store, customer_user, ensure_escrow):
        wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=1,
        )
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=100,
            return_url="https://ok.com",
            external_guid="ORD-LOWBAL-1",
        )
        with pytest.raises(ValidationError):
            pay_payment_request(payment_request, customer_user, wallet)

    def test_pay_with_wrong_wallet_owner(self, store, customer_user, ensure_escrow):
        other = get_user_model().objects.create(username="other")
        wrong_wallet = Wallet.objects.create(
            user=other,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=5_000,
        )
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=100,
            return_url="https://ok.com",
            external_guid="ORD-WRONGWALLET-1",
        )
        with pytest.raises(ValidationError):
            pay_payment_request(payment_request, customer_user, wrong_wallet)

    def test_verify_wrong_status(self, store, customer_user):
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=100,
            return_url="https://ok.com",
            external_guid="ORD-WRONGSTATUS-1",
        )
        with pytest.raises(ValidationError):
            verify_payment_request(payment_request, store=store)

    def test_double_verify(
            self, store, customer_user, customer_cash_wallet, ensure_escrow
    ):
        Wallet.objects.get_or_create(
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
            external_guid="ORD-DOUBLEVERIFY-1",
        )

        payment = pay_payment_request(
            payment_request,
            customer_user,
            customer_cash_wallet,
        )

        assert payment.status == PaymentStatus.AWAITING_MERCHANT_CONFIRMATION

        first_verified_payment = verify_payment_request(payment_request, store=store)
        payment_request.refresh_from_db()
        first_verified_payment.refresh_from_db()

        assert payment_request.status == PaymentRequestStatus.COMPLETED
        assert first_verified_payment.status == PaymentStatus.COMPLETED

        with pytest.raises(ValidationError) as exc:
            verify_payment_request(payment_request, store=store)

        assert str(exc.value.detail[0]) == "این درخواست پرداخت قبلاً نهایی شده است."
        assert exc.value.get_codes()[0] == "already_completed"

    def test_double_rollback_is_idempotent(self, store, customer_user, ensure_escrow):
        customer_wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=1_000,
        )
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=100,
            return_url="https://ok.com",
            external_guid="ORD-ROLLBACK-1",
        )
        pay_payment_request(payment_request, customer_user, customer_wallet)
        payment_request.mark_expired()
        rollback_payment(payment_request)
        customer_wallet.refresh_from_db()
        before = customer_wallet.balance
        rollback_payment(payment_request)
        customer_wallet.refresh_from_db()
        assert customer_wallet.balance == before

    def test_escrow_wallet_insufficient_on_verify(
            self, store, customer_user, ensure_escrow
    ):
        customer_wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=10_000,
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
            amount=1000,
            return_url="https://ok.com",
            external_guid="ORD-ESCROW-1",
        )
        payment = pay_payment_request(payment_request, customer_user, customer_wallet)
        debit = payment.transactions.get(purpose=TransactionPurpose.ESCROW_DEBIT)
        escrow_wallet = debit.to_wallet
        escrow_wallet.balance = 0
        escrow_wallet.save(update_fields=["balance"])

        with pytest.raises(ValidationError):
            verify_payment_request(payment_request, store=store)


@pytest.mark.django_db
class TestPaymentNegativePaths:

    def test_verify_without_merchant_wallet_fails_and_state_unchanged(
            self, store, customer_user, ensure_escrow
    ):
        customer_wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=50_000,
        )
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=12_345,
            return_url="https://cb.com",
            external_guid="ORD-NOMERCHANT-1",
        )
        payment = pay_payment_request(payment_request, customer_user, customer_wallet)

        payment_request.refresh_from_db()
        assert payment_request.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.AWAITING_MERCHANT_CONFIRMATION

        with pytest.raises(ValidationError):
            verify_payment_request(payment_request, store=store)

        payment_request.refresh_from_db()
        payment.refresh_from_db()
        assert payment_request.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        assert payment.status == PaymentStatus.AWAITING_MERCHANT_CONFIRMATION

    def test_verify_awaiting_but_without_related_payment(self, store, customer_user):
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=999,
            return_url="https://ok.com",
            external_guid="ORD-MISSINGPAY-1",
        )
        payment_request.status = PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        payment_request.save(update_fields=["status"])

        with pytest.raises(ValidationError) as exc:
            verify_payment_request(payment_request, store=store)

        assert "پرداخت مرتبط" in str(exc.value)
