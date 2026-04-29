# apps/credit/api/public/v1/schema/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "add_payment_schema",
    "add_purchase_schema",
    "close_current_schema",
    "credit_limit_viewset_schema",
    "otp_request_schema",
    "otp_verify_schema",
    "report_check_schema",
    "report_latest_schema",
    "report_viewset_schema",
    "statement_line_viewset_schema",
    "statement_viewset_schema",
]

_MODULE_MAP = {
    "credit_limit_viewset_schema": (
        "apps.credit.api.public.v1.schema.credit_limit",
        "credit_limit_viewset_schema",
    ),
    "statement_viewset_schema": (
        "apps.credit.api.public.v1.schema.statement",
        "statement_viewset_schema",
    ),
    "add_purchase_schema": (
        "apps.credit.api.public.v1.schema.statement",
        "add_purchase_schema",
    ),
    "add_payment_schema": (
        "apps.credit.api.public.v1.schema.statement",
        "add_payment_schema",
    ),
    "close_current_schema": (
        "apps.credit.api.public.v1.schema.statement",
        "close_current_schema",
    ),
    "statement_line_viewset_schema": (
        "apps.credit.api.public.v1.schema.statement_line",
        "statement_line_viewset_schema",
    ),
    "otp_request_schema": (
        "apps.credit.api.public.v1.schema.loan_risk",
        "otp_request_schema",
    ),
    "otp_verify_schema": (
        "apps.credit.api.public.v1.schema.loan_risk",
        "otp_verify_schema",
    ),
    "report_viewset_schema": (
        "apps.credit.api.public.v1.schema.loan_risk",
        "report_viewset_schema",
    ),
    "report_latest_schema": (
        "apps.credit.api.public.v1.schema.loan_risk",
        "report_latest_schema",
    ),
    "report_check_schema": (
        "apps.credit.api.public.v1.schema.loan_risk",
        "report_check_schema",
    ),
}

if TYPE_CHECKING:
    from .credit_limit import credit_limit_viewset_schema
    from .loan_risk import (
        otp_request_schema,
        otp_verify_schema,
        report_check_schema,
        report_latest_schema,
        report_viewset_schema,
    )
    from .statement import (
        add_payment_schema,
        add_purchase_schema,
        close_current_schema,
        statement_viewset_schema,
    )
    from .statement_line import statement_line_viewset_schema


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
