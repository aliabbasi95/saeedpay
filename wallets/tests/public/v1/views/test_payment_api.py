# wallets/tests/public/v1/views/test_payment_api.py
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from auth_api.models import PhoneOTP
from customers.models import Customer
from merchants.models import Merchant
from profiles.models import Profile
from wallets.models import Wallet, PaymentRequest
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
    def merchant_user(self):
        User = get_user_model()
        return User.objects.create(username="merchantuser1")

    @pytest.fixture
    def merchant(self, merchant_user):
        return Merchant.objects.create(user=merchant_user, shop_name="shop1")

    @pytest.fixture
    def customer_user(self):
        user = get_user_model().objects.create(username="09128889999")
        Profile.objects.create(user=user, phone_number="09120004444")
        return user

    @pytest.fixture
    def customer(self, customer_user):
        return Customer.objects.create(user=customer_user)

    @pytest.fixture
    def customer_wallet(self, customer_user):
        return Wallet.objects.create(
            user=customer_user, kind="cash", owner_type="customer",
            balance=100000
        )

    @pytest.fixture
    def merchant_wallet(self, merchant_user):
        return Wallet.objects.create(
            user=merchant_user, kind="merchant_gateway", owner_type="merchant",
            balance=0
        )

    @pytest.fixture
    def api_client(self, customer_user):
        client = APIClient()
        client.force_authenticate(user=customer_user)
        return client

    @pytest.fixture
    def merchant_api_key(self, merchant):
        from merchants.models.apikey import MerchantApiKey
        key, key_hash = MerchantApiKey.generate_key_and_hash()
        MerchantApiKey.objects.create(
            merchant=merchant, key_hash=key_hash, is_active=True
        )
        return key

    def test_create_payment_request_api(self, merchant, merchant_api_key):
        client = APIClient()
        url = reverse("wallets_public_v1:payment-request-create")
        data = {"amount": 4321, "return_url": "https://cb.com"}
        res = client.post(
            url, data, HTTP_AUTHORIZATION=f"ApiKey {merchant_api_key}"
        )
        assert res.status_code == 201
        assert "payment_reference_code" in res.data

    def test_invalid_create_payment_request_api(
            self, merchant, merchant_api_key
            ):
        client = APIClient()
        url = reverse("wallets_public_v1:payment-request-create")
        res = client.post(
            url, {"amount": 0, "return_url": "https://cb.com"},
            HTTP_AUTHORIZATION=f"ApiKey {merchant_api_key}"
            )
        assert res.status_code == 400
        res2 = client.post(
            url, {"amount": 100, "return_url": "ftp://bad.com"},
            HTTP_AUTHORIZATION=f"ApiKey {merchant_api_key}"
            )
        assert res2.status_code == 400

    def test_payment_request_detail_api(
            self, merchant, customer_user, customer_wallet
            ):
        pr = PaymentRequest.objects.create(
            merchant=merchant.user, amount=999, return_url="https://ret.com"
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

    def test_payment_request_detail_api_unauthenticated(self, merchant):
        pr = PaymentRequest.objects.create(
            merchant=merchant.user, amount=100, return_url="https://ret.com"
        )
        url = reverse(
            "wallets_public_v1:payment-request-detail",
            args=[pr.reference_code]
            )
        client = APIClient()
        res = client.get(url)
        assert res.status_code == 200

    def test_confirm_and_verify_flow(
            self, merchant, merchant_user, customer_user, customer_wallet,
            merchant_wallet, merchant_api_key
            ):
        from wallets.services.payment import create_payment_request
        pr = create_payment_request(merchant.user, 1234, "https://cb.com")
        confirm_url = reverse(
            "wallets_public_v1:payment-request-confirm",
            args=[pr.reference_code]
            )
        verify_url = reverse(
            "wallets_public_v1:payment-request-verify",
            args=[pr.reference_code]
            )

        # Customer confirms payment
        client = APIClient()
        client.force_authenticate(user=customer_user)
        code = self.create_otp(customer_user.profile.phone_number)
        ensure_escrow_wallet_exists()
        res = client.post(
            confirm_url, {"wallet_id": customer_wallet.id, "code": code}
            )
        assert res.status_code == 200
        assert res.data["payment_reference_code"] == pr.reference_code

        # Merchant verifies payment
        client = APIClient()
        client.force_authenticate(user=merchant_user)
        res2 = client.post(verify_url)
        assert res2.status_code == 200
        assert "transaction_reference_code" in res2.data

    def test_payment_expired(self, merchant):
        import datetime
        pr = PaymentRequest.objects.create(
            merchant=merchant.user, amount=888, return_url="https://ret.com"
        )
        pr.expires_at = datetime.datetime.now().replace(year=2000)
        pr.save()
        url = reverse(
            "wallets_public_v1:payment-request-detail",
            args=[pr.reference_code]
            )
        client = APIClient()
        res = client.get(url)
        assert res.status_code == 400 or res.data.get("status") == "expired"

    def test_payment_confirm_with_wrong_wallet(
            self, merchant, customer_user, customer_wallet
            ):
        from wallets.services.payment import create_payment_request
        pr = create_payment_request(merchant.user, 1500, "https://cb.com")
        client = APIClient()
        client.force_authenticate(user=customer_user)
        other = get_user_model().objects.create(username="not_me")
        wrong_wallet = Wallet.objects.create(
            user=other, kind="cash", owner_type="customer", balance=10000
        )
        url = reverse(
            "wallets_public_v1:payment-request-confirm",
            args=[pr.reference_code]
            )
        res = client.post(url, {"wallet_id": wrong_wallet.id})
        assert res.status_code == 400

    def test_double_confirm(self, merchant, customer_user, customer_wallet):
        from wallets.services.payment import create_payment_request
        pr = create_payment_request(merchant.user, 123, "https://cb.com")
        confirm_url = reverse(
            "wallets_public_v1:payment-request-confirm",
            args=[pr.reference_code]
            )
        client = APIClient()
        client.force_authenticate(user=customer_user)
        client.post(confirm_url, {"wallet_id": customer_wallet.id})
        res2 = client.post(confirm_url, {"wallet_id": customer_wallet.id})
        assert res2.status_code == 400

    def test_double_verify(
            self, merchant, merchant_user, customer_user, customer_wallet,
            merchant_wallet
            ):
        from wallets.services.payment import create_payment_request
        pr = create_payment_request(merchant.user, 1111, "https://cb.com")
        confirm_url = reverse(
            "wallets_public_v1:payment-request-confirm",
            args=[pr.reference_code]
            )
        verify_url = reverse(
            "wallets_public_v1:payment-request-verify",
            args=[pr.reference_code]
            )
        client = APIClient()
        client.force_authenticate(user=customer_user)
        client.post(confirm_url, {"wallet_id": customer_wallet.id})
        client.force_authenticate(user=merchant_user)
        client.post(verify_url)
        res2 = client.post(verify_url)
        assert res2.status_code == 400

    def test_confirm_anonymous_forbidden(
            self, merchant, customer_user, customer_wallet
            ):
        from wallets.services.payment import create_payment_request
        pr = create_payment_request(merchant.user, 1111, "https://cb.com")
        confirm_url = reverse(
            "wallets_public_v1:payment-request-confirm",
            args=[pr.reference_code]
            )
        client = APIClient()
        res = client.post(confirm_url, {"wallet_id": customer_wallet.id})
        assert res.status_code in (401, 403)

    def test_verify_anonymous_forbidden(self, merchant):
        pr = PaymentRequest.objects.create(
            merchant=merchant.user, amount=222, return_url="https://ret.com"
        )
        verify_url = reverse(
            "wallets_public_v1:payment-request-verify",
            args=[pr.reference_code]
            )
        client = APIClient()
        res = client.post(verify_url)
        assert res.status_code in (401, 403)

    def test_confirm_insufficient_balance(self, merchant, customer_user):
        from wallets.services.payment import create_payment_request
        wallet = Wallet.objects.create(
            user=customer_user, kind="cash", owner_type="customer", balance=1
        )
        pr = create_payment_request(merchant.user, 9999, "https://cb.com")
        confirm_url = reverse(
            "wallets_public_v1:payment-request-confirm",
            args=[pr.reference_code]
            )
        client = APIClient()
        client.force_authenticate(user=customer_user)
        res = client.post(confirm_url, {"wallet_id": wallet.id})
        assert res.status_code == 400

    def test_invalid_api_key(self, merchant):
        client = APIClient()
        url = reverse("wallets_public_v1:payment-request-create")
        data = {"amount": 1000, "return_url": "https://cb.com"}
        res = client.post(url, data, HTTP_X_API_KEY="invalidkey123")
        assert res.status_code in (401, 403)
