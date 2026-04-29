# wallets/utils/consts.py

from wallets.utils.choices import OwnerType, WalletKind

ESCROW_USER_NAME = "escrow_wallet_user"
ESCROW_WALLET_KIND = "escrow"

# How long a PaymentRequest is valid after customer confirmation (merchant window)
# Keep it short; 10-20 minutes is typical. Default: 15min.
PAYMENT_REQUEST_EXPIRY_MINUTES = 15
MERCHANT_CONFIRM_WINDOW_MINUTES = 1

# Credit authorization hold expiry (if merchant doesn't confirm)
CREDIT_AUTH_HOLD_EXPIRY_MINUTES = PAYMENT_REQUEST_EXPIRY_MINUTES

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
