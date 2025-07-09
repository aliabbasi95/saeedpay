# wallets/tests/services/test_wallet_creation.py

import pytest
from django.contrib.auth import get_user_model

from wallets.models import Wallet
from wallets.services import create_default_wallets_for_user
from wallets.utils.choices import OwnerType
from wallets.utils.consts import DEFAULT_WALLETS


@pytest.mark.django_db
class TestCreateDefaultWalletsService:

    def test_wallets_created_for_customer(self):
        user = get_user_model().objects.create(username="cust1")
        create_default_wallets_for_user(user, OwnerType.CUSTOMER)

        expected_kinds = {kind for kind in DEFAULT_WALLETS[OwnerType.CUSTOMER]}
        user_wallets = Wallet.objects.filter(user=user)
        actual_kinds = {w.kind for w in user_wallets}

        assert expected_kinds == actual_kinds
        assert user_wallets.count() == len(expected_kinds)

    def test_service_idempotency(self):
        user = get_user_model().objects.create(username="cust2")
        create_default_wallets_for_user(user, OwnerType.CUSTOMER)
        create_default_wallets_for_user(user, OwnerType.CUSTOMER)

        wallet_kinds = Wallet.objects.filter(user=user).values_list(
            "kind", flat=True
        )
        assert len(wallet_kinds) == len(set(wallet_kinds))

    def test_store_wallets_empty(self):
        user = get_user_model().objects.create(username="store1")
        create_default_wallets_for_user(user, OwnerType.MERCHANT)

        assert Wallet.objects.filter(user=user).count() == 1

    def test_unsupported_owner_type_returns_empty(self):
        user = get_user_model().objects.create(username="customtype")
        create_default_wallets_for_user(user, "other-type")
        assert Wallet.objects.filter(user=user).count() == 0
