# wallets/admin/__init__.py

from .installment import InstallmentAdmin as InstallmentAdmin
from .installment_plan import InstallmentPlanAdmin as InstallmentPlanAdmin
from .payment import PaymentAdmin as PaymentAdmin
from .payment_event import PaymentEventAdmin as PaymentEventAdmin
from .payment_request import PaymentRequestAdmin as PaymentRequestAdmin
from .transaction import TransactionAdmin as TransactionAdmin
from .transfer import WalletTransferRequestAdmin as WalletTransferRequestAdmin
from .wallet import WalletAdmin as WalletAdmin

__all__ = [
    "InstallmentAdmin",
    "InstallmentPlanAdmin",
    "PaymentAdmin",
    "PaymentEventAdmin",
    "PaymentRequestAdmin",
    "TransactionAdmin",
    "WalletAdmin",
    "WalletTransferRequestAdmin",
]
