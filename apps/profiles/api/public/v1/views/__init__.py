# apps/profiles/api/public/v1/views/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "ProfileView",
    "VideoKYCSubmitView",
]

_MODULE_MAP = {
    "ProfileView": (
        "apps.profiles.api.public.v1.views.profile",
        "ProfileView",
    ),
    "VideoKYCSubmitView": (
        "apps.profiles.api.public.v1.views.video_kyc",
        "VideoKYCSubmitView",
    ),
}

if TYPE_CHECKING:
    from .profile import ProfileView
    from .video_kyc import VideoKYCSubmitView


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
