# apps/wallets/api/internal/v1/schema/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "internal_customer_wallets_by_national_id_schema",
]

_MODULE_MAP = {
    "internal_customer_wallets_by_national_id_schema": (
        "apps.wallets.api.internal.v1.schema.payment",
        "internal_customer_wallets_by_national_id_schema",
    ),
}

if TYPE_CHECKING:
    from .wallet import (
        internal_customer_wallets_by_national_id_schema,
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
