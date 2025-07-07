from .models import Wallet
from .utils.consts import DEFAULT_WALLETS


def create_default_wallets_for_user(user, owner_type):
    wallet_kinds = DEFAULT_WALLETS.get(owner_type, [])

    wallets = []
    for kind in wallet_kinds:
        wallet, _ = Wallet.objects.get_or_create(
            user=user,
            kind=kind,
            owner_type=owner_type,
        )
        wallets.append(wallet)
