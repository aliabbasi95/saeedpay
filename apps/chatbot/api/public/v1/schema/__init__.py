# chatbot/api/public/v1/schema/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "chat_action_schema",
    "chat_session_viewset_schema",
    "messages_action_schema",
]

_MODULE_MAP = {
    "chat_session_viewset_schema": (
        "chatbot.api.public.v1.schema.session",
        "chat_session_viewset_schema",
    ),
    "chat_action_schema": (
        "chatbot.api.public.v1.schema.session",
        "chat_action_schema",
    ),
    "messages_action_schema": (
        "chatbot.api.public.v1.schema.session",
        "messages_action_schema",
    ),
}

if TYPE_CHECKING:
    from .session import (
        chat_action_schema,
        chat_session_viewset_schema,
        messages_action_schema,
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
