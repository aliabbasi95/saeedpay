# wallets/api/internal/v1/views/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "InternalCustomerWalletListByNationalIdView",
]

_MODULE_MAP = {
    "InternalCustomerWalletListByNationalIdView": (
        "wallets.api.internal.v1.views.wallet",
        "InternalCustomerWalletListByNationalIdView",
    ),
}

if TYPE_CHECKING:
    from .wallet import InternalCustomerWalletListByNationalIdView


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
