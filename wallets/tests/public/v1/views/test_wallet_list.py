# wallets/tests/public/v1/views/test_wallet_list.py

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from wallets.models import Wallet
from wallets.utils.choices import OwnerType, WalletKind


@pytest.mark.django_db
class TestWalletListView:
    @pytest.fixture(autouse=True)
    def _no_throttle(self):
        cache.clear()

        settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"][
            "anon"] = "100000/hour"
        settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"][
            "user"] = "100000/hour"

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return get_user_model().objects.create(username="09120000000")

    @pytest.fixture
    def wallets(self, user):
        Wallet.objects.create(
            user=user, kind=WalletKind.CASH, owner_type=OwnerType.CUSTOMER,
            balance=100
        )
        Wallet.objects.create(
            user=user, kind=WalletKind.CREDIT, owner_type=OwnerType.CUSTOMER,
            balance=200
        )
        Wallet.objects.create(
            user=user, kind=WalletKind.CASHBACK, owner_type=OwnerType.MERCHANT,
            balance=300
        )

    def _payload(self, resp):
        return resp.data["results"] if isinstance(
            resp.data, dict
        ) and "results" in resp.data else resp.data

    def test_requires_authentication(self, client):
        response = client.get("/saeedpay/api/wallets/public/v1/wallets/")
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED,
                                        status.HTTP_403_FORBIDDEN)

    def test_list_wallets_success_customer(self, client, user, wallets):
        client.force_authenticate(user=user)
        response = client.get(
            "/saeedpay/api/wallets/public/v1/wallets/?owner_type=customer"
        )
        assert response.status_code == status.HTTP_200_OK
        items = self._payload(response)
        assert isinstance(items, list)
        assert len(items) == 2

    def test_list_wallets_success_merchant(self, client, user, wallets):
        client.force_authenticate(user=user)
        response = client.get(
            "/saeedpay/api/wallets/public/v1/wallets/?owner_type=merchant"
        )
        assert response.status_code == status.HTTP_200_OK
        items = self._payload(response)
        assert len(items) == 1
        assert items[0]["kind"] == WalletKind.CASHBACK

    def test_missing_owner_type(self, client, user):
        client.force_authenticate(user=user)
        response = client.get("/saeedpay/api/wallets/public/v1/wallets/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "owner_type" in response.data

    def test_invalid_owner_type(self, client, user):
        client.force_authenticate(user=user)
        response = client.get(
            "/saeedpay/api/wallets/public/v1/wallets/?owner_type=INVALID"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "owner_type" in response.data

    def test_wallet_list_empty_result(self, client, user):
        client.force_authenticate(user=user)
        response = client.get(
            "/saeedpay/api/wallets/public/v1/wallets/?owner_type=merchant"
        )
        assert response.status_code == status.HTTP_200_OK
        items = self._payload(response)
        assert items == []

    def test_wallet_list_ordering(self, client, user):
        for kind in WalletKind.values:
            Wallet.objects.create(
                user=user, kind=kind, owner_type=OwnerType.CUSTOMER, balance=0
            )
        client.force_authenticate(user=user)
        response = client.get(
            "/saeedpay/api/wallets/public/v1/wallets/?owner_type=customer"
        )
        items = self._payload(response)
        kinds = [w["kind"] for w in items]
        assert kinds == sorted(kinds)

    def test_wallet_list_post_not_allowed(self, client, user):
        client.force_authenticate(user=user)
        response = client.post(
            "/saeedpay/api/wallets/public/v1/wallets/", data={}
        )
        assert response.status_code in [status.HTTP_403_FORBIDDEN,
                                        status.HTTP_405_METHOD_NOT_ALLOWED]
