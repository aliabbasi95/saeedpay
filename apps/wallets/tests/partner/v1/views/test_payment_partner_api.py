# apps/wallets/tests/partner/v1/views/test_payment_partner_api.py

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from apps.merchants.models import Merchant
from apps.store.authentication import StoreApiKeyAuthentication
from apps.store.models import Store
from apps.wallets.api.partner.v1.views.payment import PartnerPaymentRequestViewSet
from apps.wallets.models import PaymentRequest, Wallet
from apps.wallets.services.payment import pay_payment_request
from apps.wallets.utils.choices import (
    OwnerType,
    PaymentFlowType,
    PaymentRequestStatus,
    PaymentStatus,
    WalletKind,
)
from apps.wallets.utils.escrow import ensure_escrow_wallet_exists


@pytest.mark.django_db
class TestPartnerPaymentRequestApi:
    def _build_partner_client(self, monkeypatch, *, store, user):
        client = APIClient()

        def fake_authenticate(self, request):
            request.store = store
            request.store_api_key = None
            return user, None

        monkeypatch.setattr(
            StoreApiKeyAuthentication,
            "authenticate",
            fake_authenticate,
        )
        return client

    def test_create_online_payment_request_success(
        self,
        monkeypatch,
        store,
        merchant_user,
        customer_user,
    ):
        customer_user.profile.national_id = "1234567890"
        customer_user.profile.save(update_fields=["national_id"])

        client = self._build_partner_client(
            monkeypatch,
            store=store,
            user=merchant_user,
        )

        url = reverse("wallets_partner_v1:partner-payment-request-list")
        response = client.post(
            url,
            {
                "amount": 250000,
                "return_url": "https://merchant.example.com/callback",
                "description": "online payment request",
                "external_guid": "ORD-1001",
                "national_id": "1234567890",
                "flow_type": PaymentFlowType.ONLINE,
            },
            format="json",
        )

        assert response.status_code == 201, response.data
        assert response.data["code"] == "payment_request_created"
        assert response.data["amount"] == 250000
        assert response.data["payment_request_status"] == PaymentRequestStatus.CREATED
        assert response.data["flow_type"] == PaymentFlowType.ONLINE
        assert response.data["payment_reference_code"]
        assert response.data["merchant_confirmation_required"] is True
        assert response.data["payment_url"].endswith(
            f"{response.data['payment_reference_code']}/"
        )

        payment_request = PaymentRequest.objects.get(
            reference_code=response.data["payment_reference_code"]
        )
        assert payment_request.store == store
        assert payment_request.customer == customer_user.customer
        assert payment_request.flow_type == PaymentFlowType.ONLINE
        assert payment_request.external_guid == "ORD-1001"
        assert payment_request.return_url == "https://merchant.example.com/callback"

    def test_create_qr_payment_request_from_partner_api_returns_400(
        self,
        monkeypatch,
        store,
        merchant_user,
        customer_user,
    ):
        customer_user.profile.national_id = "2222222222"
        customer_user.profile.save(update_fields=["national_id"])

        client = self._build_partner_client(
            monkeypatch,
            store=store,
            user=merchant_user,
        )

        url = reverse("wallets_partner_v1:partner-payment-request-list")
        response = client.post(
            url,
            {
                "amount": 78000,
                "return_url": "https://merchant.example.com/qr-callback",
                "description": "qr payment request",
                "external_guid": "POS-1",
                "national_id": "2222222222",
                "flow_type": PaymentFlowType.QR_POS,
            },
            format="json",
        )

        assert response.status_code == 400, response.data
        assert "flow_type" in response.data

    def test_create_payment_request_customer_not_found_returns_404(
        self,
        monkeypatch,
        store,
        merchant_user,
    ):
        client = self._build_partner_client(
            monkeypatch,
            store=store,
            user=merchant_user,
        )

        url = reverse("wallets_partner_v1:partner-payment-request-list")
        response = client.post(
            url,
            {
                "amount": 50000,
                "return_url": "https://merchant.example.com/callback",
                "description": "missing customer",
                "external_guid": "ORD-404",
                "national_id": "9999999999",
                "flow_type": PaymentFlowType.ONLINE,
            },
            format="json",
        )

        assert response.status_code == 404
        assert response.data["code"] == "customer_not_found"
        assert response.data["detail"] == "مشتری با این کد ملی یافت نشد."

    def test_retrieve_payment_request_detail_success(
        self,
        monkeypatch,
        store,
        merchant_user,
        customer_user,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=120000,
            return_url="https://merchant.example.com/callback",
            external_guid="ORD-DETAIL-1",
            description="detail test",
            flow_type=PaymentFlowType.ONLINE,
        )

        client = self._build_partner_client(
            monkeypatch,
            store=store,
            user=merchant_user,
        )

        url = reverse(
            "wallets_partner_v1:partner-payment-request-detail",
            args=[payment_request.reference_code],
        )
        response = client.get(url)

        assert response.status_code == 200, response.data
        assert response.data["reference_code"] == payment_request.reference_code
        assert response.data["amount"] == 120000
        assert response.data["flow_type"] == PaymentFlowType.ONLINE
        assert response.data["merchant_confirmation_required"] is True
        assert response.data["store_id"] == store.id
        assert response.data["store_name"] == store.name

    def test_retrieve_expired_payment_request_marks_it_expired(
        self,
        monkeypatch,
        store,
        merchant_user,
        customer_user,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=33000,
            return_url="https://merchant.example.com/callback",
            external_guid="ORD-EXPIRED-1",
            expires_at=timezone.localtime(timezone.now())
            - timezone.timedelta(minutes=5),
            flow_type=PaymentFlowType.ONLINE,
        )

        client = self._build_partner_client(
            monkeypatch,
            store=store,
            user=merchant_user,
        )

        url = reverse(
            "wallets_partner_v1:partner-payment-request-detail",
            args=[payment_request.reference_code],
        )
        response = client.get(url)

        assert response.status_code == 200, response.data

        payment_request.refresh_from_db()
        assert payment_request.status == PaymentRequestStatus.EXPIRED
        assert response.data["status"] == PaymentRequestStatus.EXPIRED

    def test_verify_online_payment_success(
        self,
        monkeypatch,
        store,
        merchant_user,
        customer_user,
        customer_cash_wallet,
    ):
        ensure_escrow_wallet_exists()

        Wallet.objects.get_or_create(
            user=store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
            defaults={"balance": 0},
        )

        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=45000,
            return_url="https://merchant.example.com/callback",
            external_guid="ORD-VERIFY-1",
            flow_type=PaymentFlowType.ONLINE,
        )

        payment = pay_payment_request(
            payment_request,
            customer_user,
            customer_cash_wallet,
        )
        payment.refresh_from_db()
        payment_request.refresh_from_db()

        assert payment.status == PaymentStatus.AWAITING_MERCHANT_CONFIRMATION
        assert (
            payment_request.status
            == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        )

        client = self._build_partner_client(
            monkeypatch,
            store=store,
            user=merchant_user,
        )

        url = reverse(
            "wallets_partner_v1:partner-payment-request-verify",
            args=[payment_request.reference_code],
        )
        response = client.post(url, {}, format="json")

        assert response.status_code == 200, response.data
        assert response.data["detail"] == "پرداخت نهایی شد."
        assert response.data["code"] == "payment_verified"
        assert response.data["payment_reference_code"] == payment_request.reference_code
        assert response.data["payment_status"] == PaymentStatus.COMPLETED
        assert response.data["payment_request_status"] == PaymentRequestStatus.COMPLETED
        assert response.data["next_action"] == "none"
        assert response.data["merchant_confirmation_required"] is True
        assert response.data["amount"] == payment_request.amount

        payment.refresh_from_db()
        payment_request.refresh_from_db()
        assert payment.status == PaymentStatus.COMPLETED
        assert payment_request.status == PaymentRequestStatus.COMPLETED

    def test_verify_with_wrong_store_returns_404(
        self,
        monkeypatch,
        store,
        merchant_user,
        customer_user,
        customer_cash_wallet,
        user_factory,
    ):
        ensure_escrow_wallet_exists()

        Wallet.objects.get_or_create(
            user=store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
            defaults={"balance": 0},
        )

        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=61000,
            return_url="https://merchant.example.com/callback",
            external_guid="ORD-WRONG-STORE-1",
            flow_type=PaymentFlowType.ONLINE,
        )
        pay_payment_request(
            payment_request,
            customer_user,
            customer_cash_wallet,
        )

        other_merchant_user = user_factory("merchant_user_2")
        other_merchant = Merchant.objects.create(user=other_merchant_user)
        other_store = Store.objects.create(
            name="other-store",
            merchant=other_merchant,
        )

        client = self._build_partner_client(
            monkeypatch,
            store=other_store,
            user=other_merchant_user,
        )

        url = reverse(
            "wallets_partner_v1:partner-payment-request-verify",
            args=[payment_request.reference_code],
        )
        response = client.post(url, {}, format="json")

        assert response.status_code == 404

    def test_verify_qr_pos_payment_request_returns_400(
        self,
        merchant_user,
        store,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=87500,
            flow_type=PaymentFlowType.QR_POS,
            status=PaymentRequestStatus.CREATED,
        )

        factory = APIRequestFactory()
        request = factory.post(
            f"/fake/payment-requests/{payment_request.reference_code}/verify/",
            {},
            format="json",
        )
        force_authenticate(request, user=merchant_user)
        request.store = store

        view = PartnerPaymentRequestViewSet.as_view({"post": "verify"})
        response = view(request, reference_code=payment_request.reference_code)

        assert response.status_code == 400, response.data
        assert response.data["code"] == "unsupported_flow_type"
