# wallets/utils/consts.py

from wallets.utils.choices import OwnerType, WalletKind

ESCROW_USER_NAME = "escrow_wallet_user"
ESCROW_WALLET_KIND = "escrow"

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

FRONTEND_PAYMENT_DETAIL_URL = "dashboard/payment/"
FRONTEND_INSTALLMENT_REQUEST_DETAIL_URL = "dashboard/credit-request"
