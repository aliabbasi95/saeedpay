# wallets/api/public/v1/schema/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "installment_plans_schema",
    "installments_schema",
    "merchant_pos_payment_cancel_schema",
    "merchant_pos_payment_create_schema",
    "merchant_pos_payment_list_schema",
    "merchant_pos_payment_retrieve_schema",
    "payment_confirm_schema",
    "payment_list_schema",
    "payment_retrieve_schema",
    "plan_installments_action_schema",
    "transfer_confirm_schema",
    "transfer_create_schema",
    "transfer_reject_schema",
    "transfer_retrieve_schema",
    "transfers_list_schema",
    "wallets_list_schema",
]

_MODULE_MAP = {
    "installments_schema": (
        "wallets.api.public.v1.schema.installment",
        "installments_schema",
    ),
    "installment_plans_schema": (
        "wallets.api.public.v1.schema.installment_plan",
        "installment_plans_schema",
    ),
    "plan_installments_action_schema": (
        "wallets.api.public.v1.schema.installment_plan",
        "plan_installments_action_schema",
    ),
    "merchant_pos_payment_cancel_schema": (
        "wallets.api.public.v1.schema.payment_requests",
        "merchant_pos_payment_cancel_schema",
    ),
    "merchant_pos_payment_create_schema": (
        "wallets.api.public.v1.schema.payment_requests",
        "merchant_pos_payment_create_schema",
    ),
    "merchant_pos_payment_list_schema": (
        "wallets.api.public.v1.schema.payment_requests",
        "merchant_pos_payment_list_schema",
    ),
    "merchant_pos_payment_retrieve_schema": (
        "wallets.api.public.v1.schema.payment_requests",
        "merchant_pos_payment_retrieve_schema",
    ),
    "payment_confirm_schema": (
        "wallets.api.public.v1.schema.payment_requests",
        "payment_confirm_schema",
    ),
    "payment_list_schema": (
        "wallets.api.public.v1.schema.payment_requests",
        "payment_list_schema",
    ),
    "payment_retrieve_schema": (
        "wallets.api.public.v1.schema.payment_requests",
        "payment_retrieve_schema",
    ),
    "transfers_list_schema": (
        "wallets.api.public.v1.schema.transfer",
        "transfers_list_schema",
    ),
    "transfer_retrieve_schema": (
        "wallets.api.public.v1.schema.transfer",
        "transfer_retrieve_schema",
    ),
    "transfer_create_schema": (
        "wallets.api.public.v1.schema.transfer",
        "transfer_create_schema",
    ),
    "transfer_confirm_schema": (
        "wallets.api.public.v1.schema.transfer",
        "transfer_confirm_schema",
    ),
    "transfer_reject_schema": (
        "wallets.api.public.v1.schema.transfer",
        "transfer_reject_schema",
    ),
    "wallets_list_schema": (
        "wallets.api.public.v1.schema.wallet",
        "wallets_list_schema",
    ),
}

if TYPE_CHECKING:
    from .installment import installments_schema
    from .installment_plan import (
        installment_plans_schema,
        plan_installments_action_schema,
    )
    from .payment_requests import (
        merchant_pos_payment_cancel_schema,
        merchant_pos_payment_create_schema,
        merchant_pos_payment_list_schema,
        merchant_pos_payment_retrieve_schema,
        payment_confirm_schema,
        payment_list_schema,
        payment_retrieve_schema,
    )
    from .transfer import (
        transfer_confirm_schema,
        transfer_create_schema,
        transfer_reject_schema,
        transfer_retrieve_schema,
        transfers_list_schema,
    )
    from .wallet import wallets_list_schema


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
