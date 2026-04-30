# apps/wallets/api/public/v1/serializers/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "InstallmentPlanSerializer",
    "InstallmentSerializer",
    "MerchantPosPaymentRequestCreateResponseSerializer",
    "MerchantPosPaymentRequestCreateSerializer",
    "MerchantPosPaymentRequestDetailSerializer",
    "MerchantPosPaymentRequestListItemSerializer",
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
        "apps.wallets.api.public.v1.serializers.wallet",
        "WalletSerializer",
    ),
    "WalletListQuerySerializer": (
        "apps.wallets.api.public.v1.serializers.wallet",
        "WalletListQuerySerializer",
    ),
    "TransactionSerializer": (
        "apps.wallets.api.public.v1.serializers.transaction",
        "TransactionSerializer",
    ),
    "WalletTransferCreateSerializer": (
        "apps.wallets.api.public.v1.serializers.transfer",
        "WalletTransferCreateSerializer",
    ),
    "WalletTransferDetailSerializer": (
        "apps.wallets.api.public.v1.serializers.transfer",
        "WalletTransferDetailSerializer",
    ),
    "WalletTransferConfirmSerializer": (
        "apps.wallets.api.public.v1.serializers.transfer",
        "WalletTransferConfirmSerializer",
    ),
    "InstallmentPlanSerializer": (
        "apps.wallets.api.public.v1.serializers.installment_plan",
        "InstallmentPlanSerializer",
    ),
    "InstallmentSerializer": (
        "apps.wallets.api.public.v1.serializers.installment",
        "InstallmentSerializer",
    ),
    "PaymentActionResponseSerializer": (
        "apps.wallets.api.public.v1.serializers.payment",
        "PaymentActionResponseSerializer",
    ),
    "PaymentConfirmResponseSerializer": (
        "apps.wallets.api.public.v1.serializers.payment",
        "PaymentConfirmResponseSerializer",
    ),
    "PaymentConfirmSerializer": (
        "apps.wallets.api.public.v1.serializers.payment",
        "PaymentConfirmSerializer",
    ),
    "PaymentRequestDetailSerializer": (
        "apps.wallets.api.public.v1.serializers.payment",
        "PaymentRequestDetailSerializer",
    ),
    "PaymentRequestDetailWithWalletsSerializer": (
        "apps.wallets.api.public.v1.serializers.payment",
        "PaymentRequestDetailWithWalletsSerializer",
    ),
    "PaymentRequestListItemSerializer": (
        "apps.wallets.api.public.v1.serializers.payment",
        "PaymentRequestListItemSerializer",
    ),
    "MerchantPosPaymentRequestCreateSerializer": (
        "apps.wallets.api.public.v1.serializers.payment_pos",
        "MerchantPosPaymentRequestCreateSerializer",
    ),
    "MerchantPosPaymentRequestListItemSerializer": (
        "apps.wallets.api.public.v1.serializers.payment_pos",
        "MerchantPosPaymentRequestListItemSerializer",
    ),
    "MerchantPosPaymentRequestDetailSerializer": (
        "apps.wallets.api.public.v1.serializers.payment_pos",
        "MerchantPosPaymentRequestDetailSerializer",
    ),
    "MerchantPosPaymentRequestCreateResponseSerializer": (
        "apps.wallets.api.public.v1.serializers.payment_pos",
        "MerchantPosPaymentRequestCreateResponseSerializer",
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
    from .payment_pos import (
        MerchantPosPaymentRequestCreateResponseSerializer,
        MerchantPosPaymentRequestCreateSerializer,
        MerchantPosPaymentRequestDetailSerializer,
        MerchantPosPaymentRequestListItemSerializer,
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
