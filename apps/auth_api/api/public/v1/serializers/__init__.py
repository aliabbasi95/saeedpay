# auth_api/api/public/v1/serializers/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "ChangePasswordSerializer",
    "LoginSerializer",
    "SendOTPSerializer",
    "SendUserOTPSerializer",
    "RegisterCustomerSerializer",
    "RegisterMerchantSerializer",
    "ResetPasswordSerializer",
]

_MODULE_MAP = {
    "ChangePasswordSerializer": (
        "auth_api.api.public.v1.serializers.change_password",
        "ChangePasswordSerializer",
    ),
    "LoginSerializer": (
        "auth_api.api.public.v1.serializers.login",
        "LoginSerializer",
    ),
    "SendOTPSerializer": (
        "auth_api.api.public.v1.serializers.otp",
        "SendOTPSerializer",
    ),
    "SendUserOTPSerializer": (
        "auth_api.api.public.v1.serializers.otp",
        "SendUserOTPSerializer",
    ),
    "RegisterCustomerSerializer": (
        "auth_api.api.public.v1.serializers.register_customer",
        "RegisterCustomerSerializer",
    ),
    "RegisterMerchantSerializer": (
        "auth_api.api.public.v1.serializers.register_merchant",
        "RegisterMerchantSerializer",
    ),
    "ResetPasswordSerializer": (
        "auth_api.api.public.v1.serializers.reset_password",
        "ResetPasswordSerializer",
    ),
}

if TYPE_CHECKING:
    from .change_password import ChangePasswordSerializer
    from .login import LoginSerializer
    from .otp import SendOTPSerializer, SendUserOTPSerializer
    from .register_customer import RegisterCustomerSerializer
    from .register_merchant import RegisterMerchantSerializer
    from .reset_password import ResetPasswordSerializer


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
