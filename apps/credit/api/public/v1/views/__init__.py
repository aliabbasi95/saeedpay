# apps/credit/api/public/v1/views/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "CreditLimitViewSet",
    "LoanRiskAuthViewSet",
    "LoanRiskReportViewSet",
    "StatementLineViewSet",
    "StatementViewSet",
]

_MODULE_MAP = {
    "CreditLimitViewSet": (
        "apps.credit.api.public.v1.views.credit_limit",
        "CreditLimitViewSet",
    ),
    "LoanRiskAuthViewSet": (
        "apps.credit.api.public.v1.views.loan_risk",
        "LoanRiskAuthViewSet",
    ),
    "LoanRiskReportViewSet": (
        "apps.credit.api.public.v1.views.loan_risk",
        "LoanRiskReportViewSet",
    ),
    "StatementViewSet": (
        "apps.credit.api.public.v1.views.statement",
        "StatementViewSet",
    ),
    "StatementLineViewSet": (
        "apps.credit.api.public.v1.views.statement_line",
        "StatementLineViewSet",
    ),
}

if TYPE_CHECKING:
    from .credit_limit import CreditLimitViewSet
    from .loan_risk import LoanRiskAuthViewSet, LoanRiskReportViewSet
    from .statement import StatementViewSet
    from .statement_line import StatementLineViewSet


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
