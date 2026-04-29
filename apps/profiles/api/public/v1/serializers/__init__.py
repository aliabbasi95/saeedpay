# profiles/api/public/v1/serializers/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "ProfileSerializer",
    "VideoKYCSerializer",
]

_MODULE_MAP = {
    "ProfileSerializer": (
        "profiles.api.public.v1.serializers.profile",
        "ProfileSerializer",
    ),
    "VideoKYCSerializer": (
        "profiles.api.public.v1.serializers.video_kyc",
        "VideoKYCSerializer",
    ),
}

if TYPE_CHECKING:
    from .profile import ProfileSerializer
    from .video_kyc import VideoKYCSerializer


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
