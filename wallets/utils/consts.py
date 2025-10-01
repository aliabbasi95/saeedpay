# wallets/utils/consts.py

from wallets.utils.choices import OwnerType, WalletKind

ESCROW_USER_NAME = "escrow_wallet_user"
ESCROW_WALLET_KIND = "escrow"

PAYMENT_REQUEST_EXPIRY_MINUTES = 15

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

FRONTEND_PAYMENT_DETAIL_URL = "dashboard/payment-request/"
FRONTEND_INSTALLMENT_REQUEST_DETAIL_URL = "dashboard/credit-request"
