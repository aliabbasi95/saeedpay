# wallets/tasks/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "cleanup_cancelled_and_expired_requests",
    "expire_pending_payment_requests",
    "task_cleanup_cancelled_and_expired_requests",
    "task_expire_pending_payment_requests",
    "task_expire_pending_transfer_requests",
]

_MODULE_MAP = {
    "cleanup_cancelled_and_expired_requests": (
        "wallets.tasks.payment",
        "cleanup_cancelled_and_expired_requests",
    ),
    "expire_pending_payment_requests": (
        "wallets.tasks.payment",
        "expire_pending_payment_requests",
    ),
    "task_cleanup_cancelled_and_expired_requests": (
        "wallets.tasks.payment",
        "task_cleanup_cancelled_and_expired_requests",
    ),
    "task_expire_pending_payment_requests": (
        "wallets.tasks.payment",
        "task_expire_pending_payment_requests",
    ),
    "task_expire_pending_transfer_requests": (
        "wallets.tasks.transfer",
        "task_expire_pending_transfer_requests",
    ),
}

if TYPE_CHECKING:
    from .payment import (
        cleanup_cancelled_and_expired_requests,
        expire_pending_payment_requests,
        task_cleanup_cancelled_and_expired_requests,
        task_expire_pending_payment_requests,
    )
    from .transfer import task_expire_pending_transfer_requests


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
