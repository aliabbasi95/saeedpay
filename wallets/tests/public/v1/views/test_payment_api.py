# wallets/tests/public/v1/views/test_payment_api.py

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from auth_api.models import PhoneOTP
from wallets.models import PaymentRequest, Wallet
from wallets.services.payment import verify_payment_request
from wallets.utils.choices import OwnerType, WalletKind
from wallets.utils.escrow import ensure_escrow_wallet_exists


@pytest.mark.django_db
class TestPaymentApi:

    def create_otp(self, phone_number):
        otp = PhoneOTP.objects.create(phone_number=phone_number)
        code = otp.generate()
        otp.last_send_date = timezone.localtime()
        otp.save()
        return code

    @pytest.fixture
    def api_client(self, customer_user):
        client = APIClient()
        client.force_authenticate(user=customer_user)
        return client

    def test_payment_request_detail_api_authenticated(
            self, store, customer_user, customer_cash_wallet
    ):
        pr = PaymentRequest.objects.create(
            store=store, amount=999, return_url="https://ret.com"
        )
        url = reverse(
            "wallets_public_v1:payment-request-detail",
            args=[pr.reference_code]
        )
        client = APIClient()
        client.force_authenticate(user=customer_user)
        res = client.get(url)
        assert res.status_code == 200
        assert res.data["amount"] == 999

    def test_payment_request_detail_api_unauthenticated(self, store):
        pr = PaymentRequest.objects.create(
            store=store, amount=100, return_url="https://ret.com"
        )
        url = reverse(
            "wallets_public_v1:payment-request-detail",
            args=[pr.reference_code]
        )
        client = APIClient()
        res = client.get(url)
        assert res.status_code == 200

    def test_confirm_and_verify_flow_via_service_verify(
            self, store, customer_user, customer_cash_wallet
    ):
        pr = PaymentRequest.objects.create(
            store=store, amount=1234, return_url="https://cb.com"
        )

        confirm_url = reverse(
            "wallets_public_v1:payment-request-confirm",
            args=[pr.reference_code]
        )
        client = APIClient()
        client.force_authenticate(user=customer_user)

        ensure_escrow_wallet_exists()
        code = self.create_otp(customer_user.profile.phone_number)
        res = client.post(
            confirm_url, {"wallet_id": customer_cash_wallet.id, "code": code}
        )
        assert res.status_code == 200
        assert res.data["payment_reference_code"] == pr.reference_code

        from wallets.utils.choices import PaymentRequestStatus
        pr.refresh_from_db()
        assert pr.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION

        from wallets.models import Wallet
        from wallets.utils.choices import WalletKind, OwnerType
        Wallet.objects.get_or_create(
            user=store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
            defaults={"balance": 0},
        )

        verify_payment_request(pr)
        pr.refresh_from_db()
        assert pr.status == PaymentRequestStatus.COMPLETED

    def test_payment_expired_detail(self, store):
        import datetime
        pr = PaymentRequest.objects.create(
            store=store, amount=888, return_url="https://ret.com"
        )
        pr.expires_at = datetime.datetime.now(
            tz=datetime.timezone.utc
        ).replace(year=2000)

        pr.save()
        url = reverse(
            "wallets_public_v1:payment-request-detail",
            args=[pr.reference_code]
        )
        client = APIClient()
        res = client.get(url)
        assert res.status_code in (400, 200)

    def test_confirm_with_wrong_wallet(
            self, store, customer_user, customer_cash_wallet
    ):
        from django.contrib.auth import get_user_model
        from wallets.models import Wallet
        other = get_user_model().objects.create(username="not_me")
        wrong_wallet = Wallet.objects.create(
            user=other, kind="cash", owner_type="customer", balance=10000
        )
        pr = PaymentRequest.objects.create(
            store=store, amount=1500, return_url="https://cb.com"
        )
        client = APIClient()
        client.force_authenticate(user=customer_user)
        confirm_url = reverse(
            "wallets_public_v1:payment-request-confirm",
            args=[pr.reference_code]
        )
        code = self.create_otp(customer_user.profile.phone_number)
        res = client.post(
            confirm_url, {"wallet_id": wrong_wallet.id, "code": code}
        )
        assert res.status_code == 400

    def test_double_confirm(self, store, customer_user, customer_cash_wallet):
        pr = PaymentRequest.objects.create(
            store=store, amount=123, return_url="https://cb.com"
        )
        confirm_url = reverse(
            "wallets_public_v1:payment-request-confirm",
            args=[pr.reference_code]
        )
        client = APIClient()
        client.force_authenticate(user=customer_user)
        code1 = self.create_otp(customer_user.profile.phone_number)
        _ = client.post(
            confirm_url, {"wallet_id": customer_cash_wallet.id, "code": code1}
        )
        code2 = self.create_otp(customer_user.profile.phone_number)
        res2 = client.post(
            confirm_url, {
                "wallet_id": customer_cash_wallet.id, "code": code2
            }
        )
        assert res2.status_code == 400

    def test_confirm_anonymous_forbidden(self, store, customer_cash_wallet):
        pr = PaymentRequest.objects.create(
            store=store, amount=1111, return_url="https://cb.com"
        )
        confirm_url = reverse(
            "wallets_public_v1:payment-request-confirm",
            args=[pr.reference_code]
        )
        client = APIClient()
        res = client.post(
            confirm_url, {
                "wallet_id": customer_cash_wallet.id, "code": "000000"
            }
        )
        assert res.status_code in (401, 403)

    def test_payment_request_detail_has_available_wallets_for_authenticated_user(
            self, store, customer_user
    ):
        rich = Wallet.objects.create(
            user=customer_user, kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER, balance=50_000
        )
        poor = Wallet.objects.create(
            user=customer_user, kind=WalletKind.CREDIT,
            owner_type=OwnerType.CUSTOMER, balance=100
        )
        pr = PaymentRequest.objects.create(
            store=store, amount=10_000, return_url="https://cb.com"
        )

        url = reverse(
            "wallets_public_v1:payment-request-detail",
            args=[pr.reference_code]
        )
        c = APIClient()
        c.force_authenticate(user=customer_user)
        res = c.get(url)
        assert res.status_code == 200
        assert "available_wallets" in res.data
        ids = {w["id"] for w in res.data["available_wallets"]}
        assert rich.id in ids
        assert poor.id not in ids
        assert all(
            w["owner_type"] == OwnerType.CUSTOMER for w in
            res.data["available_wallets"]
        )

    def test_payment_confirm_with_invalid_otp_returns_400(
            self, store, customer_user, customer_cash_wallet
    ):
        pr = PaymentRequest.objects.create(
            store=store, amount=1000, return_url="https://cb.com"
        )
        url = reverse(
            "wallets_public_v1:payment-request-confirm",
            args=[pr.reference_code]
        )
        c = APIClient()
        c.force_authenticate(user=customer_user)
        res = c.post(
            url, {"wallet_id": customer_cash_wallet.id, "code": "000000"}
        )
        assert res.status_code == 400

    def test_payment_confirm_404_when_reference_not_found(
            self, customer_user, customer_cash_wallet
    ):
        url = reverse(
            "wallets_public_v1:payment-request-confirm", args=["PR-NOT-EXISTS"]
        )
        c = APIClient()
        c.force_authenticate(user=customer_user)
        res = c.post(
            url, {"wallet_id": customer_cash_wallet.id, "code": "000000"}
        )
        assert res.status_code in (404, 400)

    def test_payment_request_detail_expired_contains_return_url(
            self, store
    ):
        import datetime
        pr = PaymentRequest.objects.create(
            store=store, amount=888, return_url="https://ret.com"
        )
        pr.expires_at = datetime.datetime.now(datetime.timezone.utc).replace(
            year=2000
        )
        pr.save(update_fields=["expires_at"])

        url = reverse(
            "wallets_public_v1:payment-request-detail",
            args=[pr.reference_code]
        )
        c = APIClient()
        res = c.get(url)
        assert res.status_code in (400, 200)
        assert "return_url" in res.data
        assert res.data["return_url"] == "https://ret.com"

    def test_detail_404_when_reference_not_found(self):
        client = APIClient()
        url = reverse(
            "wallets_public_v1:payment-request-detail", args=["PR404XYZ"]
        )
        res = client.get(url)
        assert res.status_code == 404

    def test_detail_no_available_wallets_for_anonymous(self, store):
        pr = PaymentRequest.objects.create(
            store=store, amount=777, return_url="https://ret.com"
        )
        client = APIClient()
        url = reverse(
            "wallets_public_v1:payment-request-detail",
            args=[pr.reference_code]
        )
        res = client.get(url)
        assert res.status_code == 200
        assert "available_wallets" not in res.data

    def test_detail_filters_by_available_balance_not_total_balance(
            self, store, customer_user
    ):
        rich_but_reserved = Wallet.objects.create(
            user=customer_user, kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=100_000, reserved_balance=90_000
        )
        truly_available = Wallet.objects.create(
            user=customer_user, kind=WalletKind.CREDIT,
            owner_type=OwnerType.CUSTOMER,
            balance=0
        )
        pr = PaymentRequest.objects.create(
            store=store, amount=20_000, return_url="https://ret.com"
        )
        client = APIClient()
        client.force_authenticate(user=customer_user)
        url = reverse(
            "wallets_public_v1:payment-request-detail",
            args=[pr.reference_code]
        )
        res = client.get(url)
        assert res.status_code == 200
        wallets = res.data.get("available_wallets", [])

        assert all(w["id"] not in (rich_but_reserved.id,) for w in wallets)

    def test_confirm_invalid_otp(
            self, store, customer_user, customer_cash_wallet
    ):
        pr = PaymentRequest.objects.create(
            store=store, amount=1_000, return_url="https://cb.com"
        )
        client = APIClient()
        client.force_authenticate(user=customer_user)
        url = reverse(
            "wallets_public_v1:payment-request-confirm",
            args=[pr.reference_code]
        )
        res = client.post(
            url, {
                "wallet_id": customer_cash_wallet.id, "code": "999999"
            }
        )
        assert res.status_code == 400
        assert "code" in (res.data or {})
