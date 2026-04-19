# profiles/admin/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "KYCVideoAssetAdmin",
    "ProfileAdmin",
    "ProfileKYCAttemptAdmin",
]

_MODULE_MAP = {
    "ProfileKYCAttemptAdmin": (
        "profiles.admin.kyc_attempt",
        "ProfileKYCAttemptAdmin",
    ),
    "KYCVideoAssetAdmin": (
        "profiles.admin.kyc_video_asset",
        "KYCVideoAssetAdmin",
    ),
    "ProfileAdmin": (
        "profiles.admin.profile",
        "ProfileAdmin",
    ),
}

if TYPE_CHECKING:
    from .kyc_attempt import ProfileKYCAttemptAdmin
    from .kyc_video_asset import KYCVideoAssetAdmin
    from .profile import ProfileAdmin


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
