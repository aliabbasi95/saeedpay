# store/services/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "regenerate_store_api_key",
]

_MODULE_MAP = {
    "regenerate_store_api_key": (
        "store.services.apikey",
        "regenerate_store_api_key",
    ),
}

if TYPE_CHECKING:
    from .apikey import regenerate_store_api_key


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
