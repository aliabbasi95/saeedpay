# apps/wallets/tests/public/v1/views/test_payment_api.py

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.auth_api.models import PhoneOTP
from apps.credit.models.credit_limit import CreditLimit
from apps.customers.models import Customer
from apps.profiles.models import Profile
from apps.wallets.models import Payment, PaymentRequest, Wallet
from apps.wallets.services.payment import verify_payment_request
from apps.wallets.utils.choices import (
    OwnerType,
    PaymentFlowType,
    PaymentMethod,
    PaymentRequestStatus,
    PaymentStatus,
    WalletKind,
)
from apps.wallets.utils.escrow import ensure_escrow_wallet_exists


@pytest.mark.django_db
class TestPaymentApi:
    def create_otp(self, phone_number):
        otp = PhoneOTP.objects.create(phone_number=phone_number)
        code = otp.generate()
        otp.last_send_date = timezone.localtime()
        otp.save(update_fields=["last_send_date"])
        return code

    def setup_credit_limit(self, customer_user, approved=1_000_000):
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

    @pytest.fixture
    def api_client(self, customer_user):
        client = APIClient()
        client.force_authenticate(user=customer_user)
        return client

    def test_payment_request_detail_api_authenticated(
        self,
        store,
        customer_user,
        customer_cash_wallet,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=999,
            return_url="https://ret.com",
        )

        url = reverse(
            "wallets_public_v1:payment-request-detail",
            args=[payment_request.reference_code],
        )
        client = APIClient()
        client.force_authenticate(user=customer_user)
        response = client.get(url)

        assert response.status_code == 200
        assert response.data["amount"] == 999
        assert response.data["can_pay"] is True
        assert response.data["reason"] is None

    def test_payment_request_detail_api_unauthenticated_for_qr_is_readable_but_not_payable(
        self,
        store,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=100,
            return_url="https://ret.com",
            flow_type=PaymentFlowType.QR_POS,
        )

        url = reverse(
            "wallets_public_v1:payment-request-detail",
            args=[payment_request.reference_code],
        )
        client = APIClient()
        response = client.get(url)

        assert response.status_code == 200
        assert response.data["can_pay"] is False
        assert response.data["reason"] == "authentication_required"
        assert response.data["available_wallets"] == []

    def test_payment_request_detail_for_other_customer_is_not_payable(
        self,
        store,
        customer_user,
        user_factory,
    ):
        other_user = user_factory("other_customer_for_detail")
        Profile.objects.create(
            user=other_user,
            phone_number="09123456781",
        )
        Customer.objects.get_or_create(user=other_user)

        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=100,
            return_url="https://ret.com",
        )

        url = reverse(
            "wallets_public_v1:payment-request-detail",
            args=[payment_request.reference_code],
        )
        client = APIClient()
        client.force_authenticate(user=other_user)
        response = client.get(url)

        assert response.status_code == 200
        assert response.data["can_pay"] is False
        assert response.data["reason"] == "not_allowed"
        assert response.data["available_wallets"] == []

    def test_confirm_and_verify_flow_via_service_verify(
        self,
        store,
        customer_user,
        customer_cash_wallet,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=1234,
            return_url="https://cb.com",
        )

        confirm_url = reverse(
            "wallets_public_v1:payment-request-confirm",
            args=[payment_request.reference_code],
        )
        client = APIClient()
        client.force_authenticate(user=customer_user)

        ensure_escrow_wallet_exists()
        code = self.create_otp(customer_user.profile.phone_number)
        response = client.post(
            confirm_url,
            {"wallet_id": customer_cash_wallet.id, "code": code},
        )

        assert response.status_code == 200
        assert response.data["code"] == "payment_confirmed"
        assert response.data["payment_reference_code"] == payment_request.reference_code
        assert response.data["next_action"] == "waiting_for_store_confirmation"
        assert (
            response.data["payment_status"]
            == PaymentStatus.AWAITING_MERCHANT_CONFIRMATION
        )
        assert (
            response.data["payment_request_status"]
            == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        )
        assert response.data["merchant_confirmation_required"] is True
        assert response.data["return_url"] == payment_request.return_url
        assert response.data["amount"] == payment_request.amount

        payment_request.refresh_from_db()
        assert (
            payment_request.status
            == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        )

        Wallet.objects.get_or_create(
            user=store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
            defaults={"balance": 0},
        )

        verify_payment_request(payment_request, store=store)
        payment_request.refresh_from_db()
        assert payment_request.status == PaymentRequestStatus.COMPLETED

    def test_qr_confirm_finishes_immediately_for_unbound_request(
        self,
        store,
        customer_user,
        customer_cash_wallet,
    ):
        Wallet.objects.get_or_create(
            user=store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
            defaults={"balance": 0},
        )

        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=1234,
            return_url="https://cb.com",
            flow_type=PaymentFlowType.QR_POS,
        )

        confirm_url = reverse(
            "wallets_public_v1:payment-request-confirm",
            args=[payment_request.reference_code],
        )
        client = APIClient()
        client.force_authenticate(user=customer_user)

        ensure_escrow_wallet_exists()
        code = self.create_otp(customer_user.profile.phone_number)
        response = client.post(
            confirm_url,
            {"wallet_id": customer_cash_wallet.id, "code": code},
        )

        assert response.status_code == 200
        assert response.data["code"] == "payment_confirmed"
        assert response.data["next_action"] == "none"
        assert response.data["merchant_confirmation_required"] is False
        assert response.data["payment_status"] == PaymentStatus.COMPLETED
        assert response.data["payment_request_status"] == PaymentRequestStatus.COMPLETED

        payment_request.refresh_from_db()
        assert payment_request.status == PaymentRequestStatus.COMPLETED
        assert payment_request.paid_by == customer_user
        assert payment_request.paid_wallet == customer_cash_wallet

    def test_confirm_bound_request_by_other_customer_is_rejected(
        self,
        store,
        customer_user,
        user_factory,
    ):
        other_user = user_factory("other_customer_confirm")
        Profile.objects.create(
            user=other_user,
            phone_number="09123456782",
        )
        Customer.objects.get_or_create(user=other_user)

        other_wallet = Wallet.objects.create(
            user=other_user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=50_000,
        )

        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=1234,
            return_url="https://cb.com",
        )

        confirm_url = reverse(
            "wallets_public_v1:payment-request-confirm",
            args=[payment_request.reference_code],
        )
        client = APIClient()
        client.force_authenticate(user=other_user)

        code = self.create_otp("09123456782")
        response = client.post(
            confirm_url,
            {"wallet_id": other_wallet.id, "code": code},
        )

        assert response.status_code == 400, response.data
        assert response.data["code"] == "payment_request_not_allowed"

        payment_request.refresh_from_db()
        assert payment_request.status == PaymentRequestStatus.CREATED

    def test_payment_request_detail_has_available_wallets_for_authenticated_user(
        self,
        store,
        customer_user,
    ):
        rich_cash_wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=50_000,
        )
        poor_credit_wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CREDIT,
            owner_type=OwnerType.CUSTOMER,
            balance=0,
        )
        self.setup_credit_limit(customer_user, approved=5_000)

        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=10_000,
            return_url="https://cb.com",
        )

        url = reverse(
            "wallets_public_v1:payment-request-detail",
            args=[payment_request.reference_code],
        )
        client = APIClient()
        client.force_authenticate(user=customer_user)
        response = client.get(url)

        assert response.status_code == 200
        ids = {wallet["id"] for wallet in response.data["available_wallets"]}
        assert rich_cash_wallet.id in ids
        assert poor_credit_wallet.id not in ids

    def test_payment_request_detail_includes_credit_wallet_when_limit_is_enough(
        self,
        store,
        customer_user,
    ):
        Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CREDIT,
            owner_type=OwnerType.CUSTOMER,
            balance=0,
        )
        self.setup_credit_limit(customer_user, approved=100_000)

        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=20_000,
            return_url="https://cb.com",
        )

        url = reverse(
            "wallets_public_v1:payment-request-detail",
            args=[payment_request.reference_code],
        )
        client = APIClient()
        client.force_authenticate(user=customer_user)
        response = client.get(url)

        assert response.status_code == 200
        wallets = response.data["available_wallets"]
        assert any(wallet["kind"] == WalletKind.CREDIT for wallet in wallets)

    def test_confirm_payment_returns_already_completed_when_completed_payment_exists(
        self,
        customer_user,
        customer_cash_wallet,
        store,
        monkeypatch,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=50_000,
            flow_type=PaymentFlowType.ONLINE,
            status=PaymentRequestStatus.COMPLETED,
            return_url="https://example.com/return",
            external_guid="ORD-DONE-1",
        )
        Payment.objects.create(
            payment_request=payment_request,
            payer=customer_user,
            payer_wallet=customer_cash_wallet,
            amount=payment_request.amount,
            method=PaymentMethod.CASH,
            flow_type=payment_request.flow_type,
            status=PaymentStatus.COMPLETED,
        )

        otp = PhoneOTP.objects.create(phone_number=customer_user.profile.phone_number)
        monkeypatch.setattr(otp, "verify", lambda code: True)
        monkeypatch.setattr(PhoneOTP.objects, "get", lambda **kwargs: otp)

        client = APIClient()
        client.force_authenticate(user=customer_user)

        url = reverse(
            "wallets_public_v1:payment-request-confirm",
            args=[payment_request.reference_code],
        )
        response = client.post(
            url,
            {
                "wallet_id": customer_cash_wallet.id,
                "code": "1234",
            },
            format="json",
        )

        assert response.status_code == 400, response.data
        assert response.data["code"] == "already_completed"

    def test_confirm_payment_returns_payment_in_progress_when_active_payment_exists(
        self,
        customer_user,
        customer_cash_wallet,
        store,
        monkeypatch,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=50_000,
            flow_type=PaymentFlowType.ONLINE,
            status=PaymentRequestStatus.CREATED,
            return_url="https://example.com/return",
            external_guid="ORD-INPROGRESS-1",
        )
        Payment.objects.create(
            payment_request=payment_request,
            payer=customer_user,
            payer_wallet=customer_cash_wallet,
            amount=payment_request.amount,
            method=PaymentMethod.CASH,
            flow_type=payment_request.flow_type,
            status=PaymentStatus.AUTHORIZED,
        )

        otp = PhoneOTP.objects.create(phone_number=customer_user.profile.phone_number)
        monkeypatch.setattr(otp, "verify", lambda code: True)
        monkeypatch.setattr(PhoneOTP.objects, "get", lambda **kwargs: otp)

        client = APIClient()
        client.force_authenticate(user=customer_user)

        url = reverse(
            "wallets_public_v1:payment-request-confirm",
            args=[payment_request.reference_code],
        )
        response = client.post(
            url,
            {
                "wallet_id": customer_cash_wallet.id,
                "code": "1234",
            },
            format="json",
        )

        assert response.status_code == 400, response.data
        assert response.data["code"] == "payment_in_progress"
