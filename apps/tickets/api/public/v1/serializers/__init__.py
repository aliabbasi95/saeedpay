# apps/tickets/api/public/v1/serializers/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "TicketCategoryDetailSerializer",
    "TicketCategoryListSerializer",
    "TicketCreateSerializer",
    "TicketMessageCreateSerializer",
    "TicketMessageSerializer",
    "TicketSerializer",
]

_MODULE_MAP = {
    "TicketCategoryListSerializer": (
        "apps.tickets.api.public.v1.serializers.category",
        "TicketCategoryListSerializer",
    ),
    "TicketCategoryDetailSerializer": (
        "apps.tickets.api.public.v1.serializers.category",
        "TicketCategoryDetailSerializer",
    ),
    "TicketSerializer": (
        "apps.tickets.api.public.v1.serializers.ticket",
        "TicketSerializer",
    ),
    "TicketCreateSerializer": (
        "apps.tickets.api.public.v1.serializers.ticket",
        "TicketCreateSerializer",
    ),
    "TicketMessageSerializer": (
        "apps.tickets.api.public.v1.serializers.ticket",
        "TicketMessageSerializer",
    ),
    "TicketMessageCreateSerializer": (
        "apps.tickets.api.public.v1.serializers.ticket",
        "TicketMessageCreateSerializer",
    ),
}

if TYPE_CHECKING:
    from .category import (
        TicketCategoryDetailSerializer,
        TicketCategoryListSerializer,
    )
    from .ticket import (
        TicketCreateSerializer,
        TicketMessageCreateSerializer,
        TicketMessageSerializer,
        TicketSerializer,
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
