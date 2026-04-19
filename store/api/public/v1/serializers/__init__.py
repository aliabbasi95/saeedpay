# store/api/public/v1/serializers/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "PublicStoreSerializer",
    "StoreApiKeyRegenerateResponseSerializer",
    "StoreCreateSerializer",
    "StoreSerializer",
]

_MODULE_MAP = {
    "StoreApiKeyRegenerateResponseSerializer": (
        "store.api.public.v1.serializers.apikey",
        "StoreApiKeyRegenerateResponseSerializer",
    ),
    "StoreSerializer": (
        "store.api.public.v1.serializers.store",
        "StoreSerializer",
    ),
    "StoreCreateSerializer": (
        "store.api.public.v1.serializers.store",
        "StoreCreateSerializer",
    ),
    "PublicStoreSerializer": (
        "store.api.public.v1.serializers.store",
        "PublicStoreSerializer",
    ),
}

if TYPE_CHECKING:
    from .apikey import StoreApiKeyRegenerateResponseSerializer
    from .store import PublicStoreSerializer, StoreCreateSerializer, StoreSerializer


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
