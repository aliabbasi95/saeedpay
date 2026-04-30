# apps/wallets/api/partner/v1/serializers/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "PaymentActionResponseSerializer",
    "PaymentRequestCreateResponseSerializer",
    "PaymentRequestCreateSerializer",
    "PaymentRequestPartnerDetailSerializer",
    "PaymentVerifyResponseSerializer",
]

_MODULE_MAP = {
    "PaymentActionResponseSerializer": (
        "apps.wallets.api.partner.v1.serializers.payment",
        "PaymentActionResponseSerializer",
    ),
    "PaymentRequestCreateResponseSerializer": (
        "apps.wallets.api.partner.v1.serializers.payment",
        "PaymentRequestCreateResponseSerializer",
    ),
    "PaymentRequestCreateSerializer": (
        "apps.wallets.api.partner.v1.serializers.payment",
        "PaymentRequestCreateSerializer",
    ),
    "PaymentRequestPartnerDetailSerializer": (
        "apps.wallets.api.partner.v1.serializers.payment",
        "PaymentRequestPartnerDetailSerializer",
    ),
    "PaymentVerifyResponseSerializer": (
        "apps.wallets.api.partner.v1.serializers.payment",
        "PaymentVerifyResponseSerializer",
    ),
}

if TYPE_CHECKING:
    from .payment import (
        PaymentActionResponseSerializer,
        PaymentRequestCreateResponseSerializer,
        PaymentRequestCreateSerializer,
        PaymentRequestPartnerDetailSerializer,
        PaymentVerifyResponseSerializer,
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
