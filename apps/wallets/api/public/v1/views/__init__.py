# wallets/api/public/v1/views/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "InstallmentPlanViewSet",
    "InstallmentViewSet",
    "MerchantPosPaymentRequestViewSet",
    "PaymentRequestViewSet",
    "WalletTransferViewSet",
    "WalletViewSet",
]

_MODULE_MAP = {
    "InstallmentViewSet": (
        "wallets.api.public.v1.views.installment",
        "InstallmentViewSet",
    ),
    "InstallmentPlanViewSet": (
        "wallets.api.public.v1.views.installment_plan",
        "InstallmentPlanViewSet",
    ),
    "PaymentRequestViewSet": (
        "wallets.api.public.v1.views.payment",
        "PaymentRequestViewSet",
    ),
    "MerchantPosPaymentRequestViewSet": (
        "wallets.api.public.v1.views.payment_pos",
        "MerchantPosPaymentRequestViewSet",
    ),
    "WalletTransferViewSet": (
        "wallets.api.public.v1.views.transfer",
        "WalletTransferViewSet",
    ),
    "WalletViewSet": (
        "wallets.api.public.v1.views.wallet",
        "WalletViewSet",
    ),
}

if TYPE_CHECKING:
    from .installment import InstallmentViewSet
    from .installment_plan import InstallmentPlanViewSet
    from .payment import PaymentRequestViewSet
    from .payment_pos import MerchantPosPaymentRequestViewSet
    from .transfer import WalletTransferViewSet
    from .wallet import WalletViewSet


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
