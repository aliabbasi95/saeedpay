# apps/wallets/services/payment/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "authorize_cash_payment",
    "authorize_credit_payment",
    "cancel_payment_request",
    "check_and_expire_payment_request",
    "cleanup_cancelled_and_expired_requests_batch",
    "create_payment_event",
    "create_payment_request",
    "expire_payment_request",
    "expire_pending_payment_requests_batch",
    "list_eligible_wallets_for_payment_request",
    "pay_payment_request",
    "resolve_payment_method",
    "rollback_cash_payment",
    "rollback_credit_payment",
    "rollback_payment",
    "settle_cash_payment",
    "settle_credit_payment",
    "validate_payment_request_payer_access",
    "validate_wallet_ownership",
    "verify_payment_request",
]

_MODULE_MAP = {
    "authorize_cash_payment": (
        "apps.wallets.services.payment.payment_authorization_service",
        "authorize_cash_payment",
    ),
    "authorize_credit_payment": (
        "apps.wallets.services.payment.payment_authorization_service",
        "authorize_credit_payment",
    ),
    "cleanup_cancelled_and_expired_requests_batch": (
        "apps.wallets.services.payment.payment_batch_service",
        "cleanup_cancelled_and_expired_requests_batch",
    ),
    "expire_pending_payment_requests_batch": (
        "apps.wallets.services.payment.payment_batch_service",
        "expire_pending_payment_requests_batch",
    ),
    "create_payment_event": (
        "apps.wallets.services.payment.payment_event",
        "create_payment_event",
    ),
    "pay_payment_request": (
        "apps.wallets.services.payment.payment_processing_service",
        "pay_payment_request",
    ),
    "rollback_payment": (
        "apps.wallets.services.payment.payment_processing_service",
        "rollback_payment",
    ),
    "verify_payment_request": (
        "apps.wallets.services.payment.payment_processing_service",
        "verify_payment_request",
    ),
    "cancel_payment_request": (
        "apps.wallets.services.payment.payment_request_service",
        "cancel_payment_request",
    ),
    "check_and_expire_payment_request": (
        "apps.wallets.services.payment.payment_request_service",
        "check_and_expire_payment_request",
    ),
    "create_payment_request": (
        "apps.wallets.services.payment.payment_request_service",
        "create_payment_request",
    ),
    "expire_payment_request": (
        "apps.wallets.services.payment.payment_request_service",
        "expire_payment_request",
    ),
    "list_eligible_wallets_for_payment_request": (
        "apps.wallets.services.payment.payment_request_service",
        "list_eligible_wallets_for_payment_request",
    ),
    "resolve_payment_method": (
        "apps.wallets.services.payment.payment_request_service",
        "resolve_payment_method",
    ),
    "validate_payment_request_payer_access": (
        "apps.wallets.services.payment.payment_request_service",
        "validate_payment_request_payer_access",
    ),
    "validate_wallet_ownership": (
        "apps.wallets.services.payment.payment_request_service",
        "validate_wallet_ownership",
    ),
    "rollback_cash_payment": (
        "apps.wallets.services.payment.payment_rollback_service",
        "rollback_cash_payment",
    ),
    "rollback_credit_payment": (
        "apps.wallets.services.payment.payment_rollback_service",
        "rollback_credit_payment",
    ),
    "settle_cash_payment": (
        "apps.wallets.services.payment.payment_settlement_service",
        "settle_cash_payment",
    ),
    "settle_credit_payment": (
        "apps.wallets.services.payment.payment_settlement_service",
        "settle_credit_payment",
    ),
}

if TYPE_CHECKING:
    from .payment_authorization_service import (
        authorize_cash_payment,
        authorize_credit_payment,
    )
    from .payment_batch_service import (
        cleanup_cancelled_and_expired_requests_batch,
        expire_pending_payment_requests_batch,
    )
    from .payment_event import create_payment_event
    from .payment_processing_service import (
        pay_payment_request,
        rollback_payment,
        verify_payment_request,
    )
    from .payment_request_service import (
        cancel_payment_request,
        check_and_expire_payment_request,
        create_payment_request,
        expire_payment_request,
        list_eligible_wallets_for_payment_request,
        resolve_payment_method,
        validate_payment_request_payer_access,
        validate_wallet_ownership,
    )
    from .payment_rollback_service import rollback_cash_payment, rollback_credit_payment
    from .payment_settlement_service import settle_cash_payment, settle_credit_payment


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
