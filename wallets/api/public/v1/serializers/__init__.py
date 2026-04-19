# wallets/api/public/v1/serializers/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "InstallmentPlanSerializer",
    "InstallmentSerializer",
    "PaymentActionResponseSerializer",
    "PaymentConfirmResponseSerializer",
    "PaymentConfirmSerializer",
    "PaymentRequestDetailSerializer",
    "PaymentRequestDetailWithWalletsSerializer",
    "PaymentRequestListItemSerializer",
    "TransactionSerializer",
    "WalletListQuerySerializer",
    "WalletSerializer",
    "WalletTransferConfirmSerializer",
    "WalletTransferCreateSerializer",
    "WalletTransferDetailSerializer",
]

_MODULE_MAP = {
    "WalletSerializer": (
        "wallets.api.public.v1.serializers.wallet",
        "WalletSerializer",
    ),
    "WalletListQuerySerializer": (
        "wallets.api.public.v1.serializers.wallet",
        "WalletListQuerySerializer",
    ),
    "TransactionSerializer": (
        "wallets.api.public.v1.serializers.transaction",
        "TransactionSerializer",
    ),
    "WalletTransferCreateSerializer": (
        "wallets.api.public.v1.serializers.transfer",
        "WalletTransferCreateSerializer",
    ),
    "WalletTransferDetailSerializer": (
        "wallets.api.public.v1.serializers.transfer",
        "WalletTransferDetailSerializer",
    ),
    "WalletTransferConfirmSerializer": (
        "wallets.api.public.v1.serializers.transfer",
        "WalletTransferConfirmSerializer",
    ),
    "InstallmentPlanSerializer": (
        "wallets.api.public.v1.serializers.installment_plan",
        "InstallmentPlanSerializer",
    ),
    "InstallmentSerializer": (
        "wallets.api.public.v1.serializers.installment",
        "InstallmentSerializer",
    ),
    "PaymentActionResponseSerializer": (
        "wallets.api.public.v1.serializers.payment",
        "PaymentActionResponseSerializer",
    ),
    "PaymentConfirmResponseSerializer": (
        "wallets.api.public.v1.serializers.payment",
        "PaymentConfirmResponseSerializer",
    ),
    "PaymentConfirmSerializer": (
        "wallets.api.public.v1.serializers.payment",
        "PaymentConfirmSerializer",
    ),
    "PaymentRequestDetailSerializer": (
        "wallets.api.public.v1.serializers.payment",
        "PaymentRequestDetailSerializer",
    ),
    "PaymentRequestDetailWithWalletsSerializer": (
        "wallets.api.public.v1.serializers.payment",
        "PaymentRequestDetailWithWalletsSerializer",
    ),
    "PaymentRequestListItemSerializer": (
        "wallets.api.public.v1.serializers.payment",
        "PaymentRequestListItemSerializer",
    ),
}

if TYPE_CHECKING:
    from .installment import InstallmentSerializer
    from .installment_plan import InstallmentPlanSerializer
    from .payment import (
        PaymentActionResponseSerializer,
        PaymentConfirmResponseSerializer,
        PaymentConfirmSerializer,
        PaymentRequestDetailSerializer,
        PaymentRequestDetailWithWalletsSerializer,
        PaymentRequestListItemSerializer,
    )
    from .transaction import TransactionSerializer
    from .transfer import (
        WalletTransferConfirmSerializer,
        WalletTransferCreateSerializer,
        WalletTransferDetailSerializer,
    )
    from .wallet import WalletListQuerySerializer, WalletSerializer


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
