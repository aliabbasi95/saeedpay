# apps/auth_api/api/public/v1/schema/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "CHANGE_PASSWORD_SCHEMA",
    "LOGIN_SCHEMA",
    "LOGOUT_SCHEMA",
    "REFRESH_SCHEMA",
    "REGISTER_CUSTOMER_SCHEMA",
    "REGISTER_MERCHANT_SCHEMA",
    "RESET_PASSWORD_SCHEMA",
    "SEND_OTP_SCHEMA",
    "SEND_USER_OTP_SCHEMA",
]

_MODULE_MAP = {
    "LOGIN_SCHEMA": (
        "apps.auth_api.api.public.v1.schema.auth",
        "LOGIN_SCHEMA",
    ),
    "LOGOUT_SCHEMA": (
        "apps.auth_api.api.public.v1.schema.auth",
        "LOGOUT_SCHEMA",
    ),
    "REFRESH_SCHEMA": (
        "apps.auth_api.api.public.v1.schema.auth",
        "REFRESH_SCHEMA",
    ),
    "SEND_OTP_SCHEMA": (
        "apps.auth_api.api.public.v1.schema.auth",
        "SEND_OTP_SCHEMA",
    ),
    "SEND_USER_OTP_SCHEMA": (
        "apps.auth_api.api.public.v1.schema.auth",
        "SEND_USER_OTP_SCHEMA",
    ),
    "REGISTER_CUSTOMER_SCHEMA": (
        "apps.auth_api.api.public.v1.schema.auth",
        "REGISTER_CUSTOMER_SCHEMA",
    ),
    "REGISTER_MERCHANT_SCHEMA": (
        "apps.auth_api.api.public.v1.schema.auth",
        "REGISTER_MERCHANT_SCHEMA",
    ),
    "CHANGE_PASSWORD_SCHEMA": (
        "apps.auth_api.api.public.v1.schema.auth",
        "CHANGE_PASSWORD_SCHEMA",
    ),
    "RESET_PASSWORD_SCHEMA": (
        "apps.auth_api.api.public.v1.schema.auth",
        "RESET_PASSWORD_SCHEMA",
    ),
}

if TYPE_CHECKING:
    from .auth import (
        CHANGE_PASSWORD_SCHEMA,
        LOGIN_SCHEMA,
        LOGOUT_SCHEMA,
        REFRESH_SCHEMA,
        REGISTER_CUSTOMER_SCHEMA,
        REGISTER_MERCHANT_SCHEMA,
        RESET_PASSWORD_SCHEMA,
        SEND_OTP_SCHEMA,
        SEND_USER_OTP_SCHEMA,
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
