# kyc/api/public/v1/schema/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "POLL_VIDEO_SCHEMA",
    "SUBMIT_VIDEO_SCHEMA",
    "VERIFY_IDENTITY_SCHEMA",
]

_MODULE_MAP = {
    "VERIFY_IDENTITY_SCHEMA": (
        "kyc.api.public.v1.schema.identity",
        "VERIFY_IDENTITY_SCHEMA",
    ),
    "SUBMIT_VIDEO_SCHEMA": (
        "kyc.api.public.v1.schema.video",
        "SUBMIT_VIDEO_SCHEMA",
    ),
    "POLL_VIDEO_SCHEMA": (
        "kyc.api.public.v1.schema.video",
        "POLL_VIDEO_SCHEMA",
    ),
}

if TYPE_CHECKING:
    from .identity import VERIFY_IDENTITY_SCHEMA
    from .video import POLL_VIDEO_SCHEMA, SUBMIT_VIDEO_SCHEMA


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
