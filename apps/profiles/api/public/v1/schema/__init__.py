# profiles/api/public/v1/schema/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "PROFILE_VIEW_SCHEMA",
    "VIDEO_KYC_SUBMIT_SCHEMA",
]

_MODULE_MAP = {
    "PROFILE_VIEW_SCHEMA": (
        "profiles.api.public.v1.schema.profile",
        "PROFILE_VIEW_SCHEMA",
    ),
    "VIDEO_KYC_SUBMIT_SCHEMA": (
        "profiles.api.public.v1.schema.video_kyc",
        "VIDEO_KYC_SUBMIT_SCHEMA",
    ),
}

if TYPE_CHECKING:
    from .profile import PROFILE_VIEW_SCHEMA
    from .video_kyc import VIDEO_KYC_SUBMIT_SCHEMA


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
