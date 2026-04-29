# kyc/services/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "IdentityAuthService",
    "get_identity_auth_service",
]

_MODULE_MAP = {
    "IdentityAuthService": (
        "kyc.services.identity_auth_service",
        "IdentityAuthService",
    ),
    "get_identity_auth_service": (
        "kyc.services.identity_auth_service",
        "get_identity_auth_service",
    ),
}

if TYPE_CHECKING:
    from .identity_auth_service import (
        IdentityAuthService,
        get_identity_auth_service,
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
