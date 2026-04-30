# apps/wallets/tests/models/test_wallet.py

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

from apps.wallets.models import Wallet
from apps.wallets.utils.choices import OwnerType, WalletKind


@pytest.mark.django_db
class TestWalletModel:
    def test_str_representation(self):
        user = get_user_model().objects.create(username="testuser")
        wallet = Wallet.objects.create(
            user=user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=150,
        )
        s = str(wallet)
        assert f"{user.username} - نقدی (مشتری)" in s

    @pytest.mark.django_db(transaction=True)
    def test_unique_constraint(self):
        user = get_user_model().objects.create(username="uniqueuser")
        Wallet.objects.create(
            user=user,
            kind=WalletKind.CREDIT,
            owner_type=OwnerType.CUSTOMER,
        )

        with pytest.raises(IntegrityError):
            Wallet.objects.create(
                user=user,
                kind=WalletKind.CREDIT,
                owner_type=OwnerType.CUSTOMER,
            )

    def test_default_balance_zero(self):
        user = get_user_model().objects.create(username="zerouser")
        wallet = Wallet.objects.create(
            user=user,
            kind=WalletKind.MICRO_CREDIT,
            owner_type=OwnerType.CUSTOMER,
        )
        assert wallet.balance == 0

    def test_created_updated_auto_fields(self):
        user = get_user_model().objects.create(username="timeuser")
        wallet = Wallet.objects.create(
            user=user,
            kind=WalletKind.CREDIT,
            owner_type=OwnerType.CUSTOMER,
        )
        now = timezone.localtime(timezone.now())
        assert now - wallet.created_at < timedelta(seconds=5)
        assert now - wallet.updated_at < timedelta(seconds=5)
