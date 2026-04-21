# wallets/api/internal/v1/serializers/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "NationalIdInputSerializer",
    "PhoneNumberInputSerializer",
    "WalletSerializer",
]

_MODULE_MAP = {
    "NationalIdInputSerializer": (
        "wallets.api.internal.v1.serializers.wallet",
        "NationalIdInputSerializer",
    ),
    "PhoneNumberInputSerializer": (
        "wallets.api.internal.v1.serializers.wallet",
        "PhoneNumberInputSerializer",
    ),
    "WalletSerializer": (
        "wallets.api.internal.v1.serializers.wallet",
        "WalletSerializer",
    ),
}

if TYPE_CHECKING:
    from .wallet import (
        NationalIdInputSerializer,
        PhoneNumberInputSerializer,
        WalletSerializer,
    )


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
