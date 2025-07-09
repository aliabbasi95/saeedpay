# wallets/utils/consts.py
from wallets.utils.choices import OwnerType, WalletKind

DEFAULT_WALLETS = {
    OwnerType.CUSTOMER: [
        WalletKind.MICRO_CREDIT,
        WalletKind.CASH,
        WalletKind.CASHBACK,
        WalletKind.CREDIT,
    ],
    OwnerType.MERCHANT: [
        WalletKind.MERCHANT_GATEWAY,
    ],
}
