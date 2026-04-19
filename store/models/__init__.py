# store/models/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "Store",
    "StoreApiKey",
    "StoreUser",
]

_MODULE_MAP = {
    "Store": (
        "store.models.store",
        "Store",
    ),
    "StoreUser": (
        "store.models.store_user",
        "StoreUser",
    ),
    "StoreApiKey": (
        "store.models.apikey",
        "StoreApiKey",
    ),
}

if TYPE_CHECKING:
    from .apikey import StoreApiKey
    from .store import Store
    from .store_user import StoreUser


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
