# chatbot/api/public/v1/serializers/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "ChatMessageSerializer",
    "ChatRequestSerializer",
    "ChatResponseSerializer",
    "ChatSessionDetailSerializer",
    "ChatSessionSerializer",
]

_MODULE_MAP = {
    "ChatMessageSerializer": (
        "chatbot.api.public.v1.serializers.message",
        "ChatMessageSerializer",
    ),
    "ChatRequestSerializer": (
        "chatbot.api.public.v1.serializers.chat",
        "ChatRequestSerializer",
    ),
    "ChatResponseSerializer": (
        "chatbot.api.public.v1.serializers.chat",
        "ChatResponseSerializer",
    ),
    "ChatSessionSerializer": (
        "chatbot.api.public.v1.serializers.session",
        "ChatSessionSerializer",
    ),
    "ChatSessionDetailSerializer": (
        "chatbot.api.public.v1.serializers.session",
        "ChatSessionDetailSerializer",
    ),
}

if TYPE_CHECKING:
    from .chat import ChatRequestSerializer, ChatResponseSerializer
    from .message import ChatMessageSerializer
    from .session import ChatSessionDetailSerializer, ChatSessionSerializer


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
