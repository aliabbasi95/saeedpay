# apps/store/api/public/v1/schema/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "public_store_list_schema",
    "public_store_retrieve_schema",
    "store_create_schema",
    "store_delete_schema",
    "store_list_schema",
    "store_partial_update_schema",
    "store_regenerate_api_key_schema",
    "store_retrieve_schema",
    "store_update_put_schema",
]

_MODULE_MAP = {
    "store_list_schema": (
        "apps.store.api.public.v1.schema.management",
        "store_list_schema",
    ),
    "store_create_schema": (
        "apps.store.api.public.v1.schema.management",
        "store_create_schema",
    ),
    "store_retrieve_schema": (
        "apps.store.api.public.v1.schema.management",
        "store_retrieve_schema",
    ),
    "store_update_put_schema": (
        "apps.store.api.public.v1.schema.management",
        "store_update_put_schema",
    ),
    "store_partial_update_schema": (
        "apps.store.api.public.v1.schema.management",
        "store_partial_update_schema",
    ),
    "store_delete_schema": (
        "apps.store.api.public.v1.schema.management",
        "store_delete_schema",
    ),
    "public_store_list_schema": (
        "apps.store.api.public.v1.schema.public",
        "public_store_list_schema",
    ),
    "public_store_retrieve_schema": (
        "apps.store.api.public.v1.schema.public",
        "public_store_retrieve_schema",
    ),
    "store_regenerate_api_key_schema": (
        "apps.store.api.public.v1.schema.apikey",
        "store_regenerate_api_key_schema",
    ),
}

if TYPE_CHECKING:
    from .apikey import store_regenerate_api_key_schema
    from .management import (
        store_create_schema,
        store_delete_schema,
        store_list_schema,
        store_partial_update_schema,
        store_retrieve_schema,
        store_update_put_schema,
    )
    from .public import public_store_list_schema, public_store_retrieve_schema


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
