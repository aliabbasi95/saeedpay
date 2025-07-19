# wallets/utils/escrow.py
from django.contrib.auth import get_user_model

from wallets.models import Wallet
from wallets.utils.choices import OwnerType
from wallets.utils.consts import ESCROW_USER_NAME, ESCROW_WALLET_KIND


def ensure_escrow_wallet_exists():
    User = get_user_model()
    user, _ = User.objects.get_or_create(username=ESCROW_USER_NAME)
    Wallet.objects.get_or_create(
        user=user,
        kind=ESCROW_WALLET_KIND,
        owner_type=OwnerType.SYSTEM,
        defaults={"balance": 0}
    )
