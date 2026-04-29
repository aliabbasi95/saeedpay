# wallets/tests/public/v1/views/test_payment_pos_api.py

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from merchants.models import Merchant
from store.models import Store
from wallets.models import PaymentEvent, PaymentRequest, Wallet
from wallets.utils.choices import (
    OwnerType,
    PaymentEventType,
    PaymentFlowType,
    PaymentRequestStatus,
    WalletKind,
)


@pytest.mark.django_db
class TestMerchantPosPaymentRequestApi:
    def test_create_pos_payment_request_success(
        self,
        merchant_user,
        store,
    ):
        client = APIClient()
        client.force_authenticate(user=merchant_user)

        url = reverse("wallets_public_v1:merchant-pos-payment-request-list")
        response = client.post(
            url,
            {
                "store_id": store.id,
                "amount": 87500,
                "description": "pos sale",
            },
            format="json",
        )

        assert response.status_code == 201, response.data
        assert response.data["code"] == "payment_request_created"
        assert response.data["payment_request_status"] == PaymentRequestStatus.CREATED
        assert response.data["flow_type"] == PaymentFlowType.QR_POS
        assert response.data["merchant_confirmation_required"] is False
        assert response.data["next_action"] == "scan_qr"
        assert response.data["qr_payload"] == response.data["payment_reference_code"]
        assert response.data["store_id"] == store.id
        assert response.data["store_name"] == store.name

        payment_request = PaymentRequest.objects.get(
            reference_code=response.data["payment_reference_code"]
        )
        assert payment_request.store == store
        assert payment_request.customer is None
        assert payment_request.flow_type == PaymentFlowType.QR_POS
        assert payment_request.external_guid is None
        assert payment_request.return_url is None

    def test_list_pos_payment_requests_only_returns_owned_qr_requests(
        self,
        merchant_user,
        store,
        user_factory,
    ):
        other_user = user_factory("other_merchant_for_pos_list")
        other_merchant = Merchant.objects.create(user=other_user)
        other_store = Store.objects.create(
            merchant=other_merchant,
            name="other-store",
        )

        qr_owned = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=1000,
            flow_type=PaymentFlowType.QR_POS,
        )
        PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=2000,
            return_url="https://example.com/2",
            external_guid="ORD-2",
            flow_type=PaymentFlowType.ONLINE,
        )
        PaymentRequest.objects.create(
            store=other_store,
            customer=None,
            amount=3000,
            flow_type=PaymentFlowType.QR_POS,
        )

        client = APIClient()
        client.force_authenticate(user=merchant_user)

        url = reverse("wallets_public_v1:merchant-pos-payment-request-list")
        response = client.get(url)

        assert response.status_code == 200, response.data
        assert response.data["count"] == 1
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["reference_code"] == qr_owned.reference_code
        assert response.data["results"][0]["flow_type"] == PaymentFlowType.QR_POS

    def test_retrieve_pos_payment_request_success(
        self,
        merchant_user,
        store,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=87500,
            description="pos sale detail",
            flow_type=PaymentFlowType.QR_POS,
        )

        client = APIClient()
        client.force_authenticate(user=merchant_user)

        url = reverse(
            "wallets_public_v1:merchant-pos-payment-request-detail",
            args=[payment_request.reference_code],
        )
        response = client.get(url)

        assert response.status_code == 200, response.data
        assert response.data["reference_code"] == payment_request.reference_code
        assert response.data["qr_payload"] == payment_request.reference_code
        assert response.data["flow_type"] == PaymentFlowType.QR_POS
        assert response.data["store_id"] == store.id
        assert response.data["store_name"] == store.name
        assert response.data["status_display"] == payment_request.get_status_display()
        assert response.data["can_cancel"] is True
        assert response.data["can_recreate"] is False
        assert response.data["status_action_hint"] == "waiting_for_customer_scan"
        assert response.data["is_paid"] is False
        assert response.data["is_expired"] is False
        assert "paid_by" not in response.data
        assert "paid_by_display" not in response.data
        assert "paid_wallet" not in response.data
        assert "paid_wallet_kind" not in response.data
        assert "paid_wallet_kind_display" not in response.data

    def test_retrieve_completed_pos_payment_request_exposes_recreate_policy_without_payer_data(
        self,
        merchant_user,
        store,
        customer_user,
    ):
        paid_wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=100_000,
        )
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=87500,
            description="completed pos sale",
            flow_type=PaymentFlowType.QR_POS,
            status=PaymentRequestStatus.COMPLETED,
            paid_by=customer_user,
            paid_wallet=paid_wallet,
        )

        client = APIClient()
        client.force_authenticate(user=merchant_user)

        url = reverse(
            "wallets_public_v1:merchant-pos-payment-request-detail",
            args=[payment_request.reference_code],
        )
        response = client.get(url)

        assert response.status_code == 200, response.data
        assert response.data["status_display"] == payment_request.get_status_display()
        assert response.data["can_cancel"] is False
        assert response.data["can_recreate"] is True
        assert response.data["status_action_hint"] == "create_new_qr"
        assert response.data["is_paid"] is True
        assert "paid_by" not in response.data
        assert "paid_by_display" not in response.data
        assert "paid_wallet" not in response.data
        assert "paid_wallet_kind" not in response.data
        assert "paid_wallet_kind_display" not in response.data

    def test_retrieve_cancelled_pos_payment_request_exposes_recreate_policy(
        self,
        merchant_user,
        store,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=87500,
            description="cancelled pos sale",
            flow_type=PaymentFlowType.QR_POS,
            status=PaymentRequestStatus.CANCELLED,
        )

        client = APIClient()
        client.force_authenticate(user=merchant_user)

        url = reverse(
            "wallets_public_v1:merchant-pos-payment-request-detail",
            args=[payment_request.reference_code],
        )
        response = client.get(url)

        assert response.status_code == 200, response.data
        assert response.data["can_cancel"] is False
        assert response.data["can_recreate"] is True
        assert response.data["status_action_hint"] == "create_new_qr"
        assert response.data["is_paid"] is False

    def test_retrieve_expired_pos_payment_request_exposes_recreate_policy(
        self,
        merchant_user,
        store,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=87500,
            description="expired pos sale",
            flow_type=PaymentFlowType.QR_POS,
            status=PaymentRequestStatus.EXPIRED,
        )

        client = APIClient()
        client.force_authenticate(user=merchant_user)

        url = reverse(
            "wallets_public_v1:merchant-pos-payment-request-detail",
            args=[payment_request.reference_code],
        )
        response = client.get(url)

        assert response.status_code == 200, response.data
        assert response.data["can_cancel"] is False
        assert response.data["can_recreate"] is True
        assert response.data["status_action_hint"] == "create_new_qr"
        assert response.data["is_expired"] is True

    def test_retrieve_pos_payment_request_of_other_merchant_returns_404(
        self,
        merchant_user,
        store,
        user_factory,
    ):
        other_user = user_factory("other_merchant_for_pos_detail")
        other_merchant = Merchant.objects.create(user=other_user)
        other_store = Store.objects.create(
            merchant=other_merchant,
            name="other-store",
        )
        payment_request = PaymentRequest.objects.create(
            store=other_store,
            customer=None,
            amount=87500,
            flow_type=PaymentFlowType.QR_POS,
        )

        client = APIClient()
        client.force_authenticate(user=merchant_user)

        url = reverse(
            "wallets_public_v1:merchant-pos-payment-request-detail",
            args=[payment_request.reference_code],
        )
        response = client.get(url)

        assert response.status_code == 404

    def test_create_pos_payment_request_for_not_owned_store_returns_404(
        self,
        merchant_user,
        store,
        user_factory,
    ):
        other_user = user_factory("other_merchant_for_pos")
        other_merchant = Merchant.objects.create(user=other_user)
        other_store = Store.objects.create(
            merchant=other_merchant,
            name="other-store",
        )

        client = APIClient()
        client.force_authenticate(user=merchant_user)

        url = reverse("wallets_public_v1:merchant-pos-payment-request-list")
        response = client.post(
            url,
            {
                "store_id": other_store.id,
                "amount": 87500,
            },
            format="json",
        )

        assert response.status_code == 404
        assert response.data["code"] == "store_not_found"

    def test_create_pos_payment_request_for_inactive_store_returns_400(
        self,
        merchant_user,
        store,
    ):
        store.is_active = False
        store.save(update_fields=["is_active"])

        client = APIClient()
        client.force_authenticate(user=merchant_user)

        url = reverse("wallets_public_v1:merchant-pos-payment-request-list")
        response = client.post(
            url,
            {
                "store_id": store.id,
                "amount": 87500,
            },
            format="json",
        )

        assert response.status_code == 400
        assert response.data["code"] == "inactive_store"

    def test_create_pos_payment_request_requires_merchant_user(
        self,
        customer_user,
        store,
    ):
        client = APIClient()
        client.force_authenticate(user=customer_user)

        url = reverse("wallets_public_v1:merchant-pos-payment-request-list")
        response = client.post(
            url,
            {
                "store_id": store.id,
                "amount": 87500,
            },
            format="json",
        )

        assert response.status_code == 403

    def test_cancel_pos_payment_request_success(
        self,
        merchant_user,
        store,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=87500,
            description="pos cancel test",
            flow_type=PaymentFlowType.QR_POS,
            status=PaymentRequestStatus.CREATED,
        )

        client = APIClient()
        client.force_authenticate(user=merchant_user)

        url = reverse(
            "wallets_public_v1:merchant-pos-payment-request-cancel",
            args=[payment_request.reference_code],
        )
        response = client.post(url, {}, format="json")

        assert response.status_code == 200, response.data
        assert response.data["code"] == "payment_request_cancelled"
        assert response.data["payment_reference_code"] == payment_request.reference_code
        assert response.data["payment_request_status"] == PaymentRequestStatus.CANCELLED
        assert response.data["merchant_confirmation_required"] is False
        assert response.data["next_action"] == "none"

        payment_request.refresh_from_db()
        assert payment_request.status == PaymentRequestStatus.CANCELLED

        event = PaymentEvent.objects.filter(
            payment_request=payment_request,
            event_type=PaymentEventType.PAYMENT_CANCELLED,
        ).latest("id")

        assert event.actor == merchant_user
        assert event.from_status == PaymentRequestStatus.CREATED
        assert event.to_status == PaymentRequestStatus.CANCELLED

    def test_cancel_pos_payment_request_of_other_merchant_returns_404(
        self,
        merchant_user,
        store,
        user_factory,
    ):
        other_user = user_factory("other_merchant_for_pos_cancel")
        other_merchant = Merchant.objects.create(user=other_user)
        other_store = Store.objects.create(
            merchant=other_merchant,
            name="other-store",
        )
        payment_request = PaymentRequest.objects.create(
            store=other_store,
            customer=None,
            amount=87500,
            flow_type=PaymentFlowType.QR_POS,
            status=PaymentRequestStatus.CREATED,
        )

        client = APIClient()
        client.force_authenticate(user=merchant_user)

        url = reverse(
            "wallets_public_v1:merchant-pos-payment-request-cancel",
            args=[payment_request.reference_code],
        )
        response = client.post(url, {}, format="json")

        assert response.status_code == 404

    def test_cancel_completed_pos_payment_request_returns_400(
        self,
        merchant_user,
        store,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=87500,
            flow_type=PaymentFlowType.QR_POS,
            status=PaymentRequestStatus.COMPLETED,
        )

        client = APIClient()
        client.force_authenticate(user=merchant_user)

        url = reverse(
            "wallets_public_v1:merchant-pos-payment-request-cancel",
            args=[payment_request.reference_code],
        )
        response = client.post(url, {}, format="json")

        assert response.status_code == 400, response.data
        assert response.data["code"] == "not_cancellable"

        payment_request.refresh_from_db()
        assert payment_request.status == PaymentRequestStatus.COMPLETED

    def test_cancel_expired_pos_payment_request_returns_400(
        self,
        merchant_user,
        store,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=87500,
            flow_type=PaymentFlowType.QR_POS,
            status=PaymentRequestStatus.EXPIRED,
        )

        client = APIClient()
        client.force_authenticate(user=merchant_user)

        url = reverse(
            "wallets_public_v1:merchant-pos-payment-request-cancel",
            args=[payment_request.reference_code],
        )
        response = client.post(url, {}, format="json")

        assert response.status_code == 400, response.data
        assert response.data["code"] == "not_cancellable"

    def test_cancel_pos_payment_request_requires_merchant_user(
        self,
        customer_user,
        store,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=87500,
            flow_type=PaymentFlowType.QR_POS,
            status=PaymentRequestStatus.CREATED,
        )

        client = APIClient()
        client.force_authenticate(user=customer_user)

        url = reverse(
            "wallets_public_v1:merchant-pos-payment-request-cancel",
            args=[payment_request.reference_code],
        )
        response = client.post(url, {}, format="json")

        assert response.status_code == 403
