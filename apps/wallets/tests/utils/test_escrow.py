# apps/wallets/tests/utils/test_escrow.py

import pytest

from apps.wallets.models import Wallet
from apps.wallets.utils.choices import OwnerType
from apps.wallets.utils.consts import ESCROW_USER_NAME, ESCROW_WALLET_KIND
from apps.wallets.utils.escrow import ensure_escrow_wallet_exists


@pytest.mark.django_db
class TestEscrowEnsure:
    def test_idempotent_creation(self):
        ensure_escrow_wallet_exists()
        w1 = Wallet.objects.get(
            user__username=ESCROW_USER_NAME, kind=ESCROW_WALLET_KIND
        )
        assert w1.owner_type == OwnerType.SYSTEM

        ensure_escrow_wallet_exists()
        w2 = Wallet.objects.get(
            user__username=ESCROW_USER_NAME, kind=ESCROW_WALLET_KIND
        )
        assert w1.id == w2.id
