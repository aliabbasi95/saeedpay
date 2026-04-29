# apps/tickets/api/public/v1/schema/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "add_message_schema",
    "messages_list_schema",
    "ticket_category_viewset_schema",
    "ticket_viewset_schema",
]

_MODULE_MAP = {
    "ticket_viewset_schema": (
        "apps.tickets.api.public.v1.schema.ticket",
        "ticket_viewset_schema",
    ),
    "messages_list_schema": (
        "apps.tickets.api.public.v1.schema.ticket",
        "messages_list_schema",
    ),
    "add_message_schema": (
        "apps.tickets.api.public.v1.schema.ticket",
        "add_message_schema",
    ),
    "ticket_category_viewset_schema": (
        "apps.tickets.api.public.v1.schema.category",
        "ticket_category_viewset_schema",
    ),
}

if TYPE_CHECKING:
    from .category import ticket_category_viewset_schema
    from .ticket import add_message_schema, messages_list_schema, ticket_viewset_schema


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
