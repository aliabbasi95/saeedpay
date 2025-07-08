# wallets/tests/public/v1/serializers/test_wallet_list.py
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from wallets.utils.choices import OwnerType
from wallets.utils.consts import DEFAULT_WALLETS


@pytest.mark.django_db
class TestWalletListAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create(
            username="testuser", password="123456"
        )
        self.client.force_authenticate(user=self.user)

    def test_wallet_list_success(self):
        from wallets.services import create_default_wallets_for_user
        create_default_wallets_for_user(self.user, OwnerType.CUSTOMER)

        response = self.client.get("/saeedpay/api/wallets/public/v1/wallets/")

        assert response.status_code == 200
        assert len(response.data) == len(DEFAULT_WALLETS[OwnerType.CUSTOMER])
        kinds = [w["kind"] for w in response.data]
        assert "cash" in kinds
