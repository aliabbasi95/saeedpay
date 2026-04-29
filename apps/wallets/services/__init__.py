# wallets/services/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "calculate_installments",
    "cancel_payment_request",
    "check_and_expire_payment_request",
    "cleanup_cancelled_and_expired_requests_batch",
    "confirm_wallet_transfer_request",
    "create_default_wallets_for_user",
    "create_payment_event",
    "create_payment_request",
    "create_wallet_transfer_request",
    "evaluate_user_credit",
    "expire_pending_payment_requests_batch",
    "expire_pending_transfer_requests",
    "expire_payment_request",
    "generate_installments_for_plan",
    "list_eligible_wallets_for_payment_request",
    "pay_installment",
    "pay_payment_request",
    "reject_wallet_transfer_request",
    "rollback_payment",
    "verify_payment_request",
]

_MODULE_MAP = {
    "create_default_wallets_for_user": (
        "wallets.services.create_wallet",
        "create_default_wallets_for_user",
    ),
    "evaluate_user_credit": (
        "wallets.services.credit",
        "evaluate_user_credit",
    ),
    "calculate_installments": (
        "wallets.services.credit",
        "calculate_installments",
    ),
    "pay_installment": (
        "wallets.services.installment",
        "pay_installment",
    ),
    "generate_installments_for_plan": (
        "wallets.services.installment",
        "generate_installments_for_plan",
    ),
    "cancel_payment_request": (
        "wallets.services.payment",
        "cancel_payment_request",
    ),
    "check_and_expire_payment_request": (
        "wallets.services.payment",
        "check_and_expire_payment_request",
    ),
    "cleanup_cancelled_and_expired_requests_batch": (
        "wallets.services.payment",
        "cleanup_cancelled_and_expired_requests_batch",
    ),
    "create_payment_event": (
        "wallets.services.payment",
        "create_payment_event",
    ),
    "create_payment_request": (
        "wallets.services.payment",
        "create_payment_request",
    ),
    "expire_payment_request": (
        "wallets.services.payment",
        "expire_payment_request",
    ),
    "expire_pending_payment_requests_batch": (
        "wallets.services.payment",
        "expire_pending_payment_requests_batch",
    ),
    "list_eligible_wallets_for_payment_request": (
        "wallets.services.payment",
        "list_eligible_wallets_for_payment_request",
    ),
    "pay_payment_request": (
        "wallets.services.payment",
        "pay_payment_request",
    ),
    "rollback_payment": (
        "wallets.services.payment",
        "rollback_payment",
    ),
    "verify_payment_request": (
        "wallets.services.payment",
        "verify_payment_request",
    ),
    "create_wallet_transfer_request": (
        "wallets.services.transfer",
        "create_wallet_transfer_request",
    ),
    "confirm_wallet_transfer_request": (
        "wallets.services.transfer",
        "confirm_wallet_transfer_request",
    ),
    "reject_wallet_transfer_request": (
        "wallets.services.transfer",
        "reject_wallet_transfer_request",
    ),
    "expire_pending_transfer_requests": (
        "wallets.services.transfer",
        "expire_pending_transfer_requests",
    ),
}

if TYPE_CHECKING:
    from .create_wallet import create_default_wallets_for_user
    from .credit import calculate_installments, evaluate_user_credit
    from .installment import generate_installments_for_plan, pay_installment
    from .payment import (
        cancel_payment_request,
        check_and_expire_payment_request,
        cleanup_cancelled_and_expired_requests_batch,
        create_payment_event,
        create_payment_request,
        expire_payment_request,
        expire_pending_payment_requests_batch,
        list_eligible_wallets_for_payment_request,
        pay_payment_request,
        rollback_payment,
        verify_payment_request,
    )
    from .transfer import (
        confirm_wallet_transfer_request,
        create_wallet_transfer_request,
        expire_pending_transfer_requests,
        reject_wallet_transfer_request,
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
