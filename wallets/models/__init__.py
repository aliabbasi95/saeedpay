# wallets/models/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "Installment",
    "InstallmentPlan",
    "Payment",
    "PaymentEvent",
    "PaymentRequest",
    "Transaction",
    "Wallet",
    "WalletTransferRequest",
]

_MODULE_MAP = {
    "Wallet": ("wallets.models.wallet", "Wallet"),
    "Payment": ("wallets.models.payment", "Payment"),
    "PaymentRequest": ("wallets.models.payment_request", "PaymentRequest"),
    "Transaction": ("wallets.models.transaction", "Transaction"),
    "WalletTransferRequest": ("wallets.models.transfer", "WalletTransferRequest"),
    "InstallmentPlan": ("wallets.models.installment_plan", "InstallmentPlan"),
    "Installment": ("wallets.models.installment", "Installment"),
    "PaymentEvent": ("wallets.models.payment_event", "PaymentEvent"),
}

if TYPE_CHECKING:
    from .installment import Installment
    from .installment_plan import InstallmentPlan
    from .payment import Payment
    from .payment_event import PaymentEvent
    from .payment_request import PaymentRequest
    from .transaction import Transaction
    from .transfer import WalletTransferRequest
    from .wallet import Wallet


def __getattr__(name: str) -> Any:
    try:
        module_path, attr_name = _MODULE_MAP[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(module_path)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(__all__)
