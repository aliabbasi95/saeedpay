# credit/api/public/v1/serializers/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "CloseStatementResponseSerializer",
    "CreditLimitSerializer",
    "LoanRiskOTPRequestSerializer",
    "LoanRiskOTPVerifySerializer",
    "LoanRiskReportDetailSerializer",
    "LoanRiskReportListSerializer",
    "LoanRiskReportSerializer",
    "StatementDetailSerializer",
    "StatementLineSerializer",
    "StatementListSerializer",
]

_MODULE_MAP = {
    "CreditLimitSerializer": (
        "credit.api.public.v1.serializers.credit",
        "CreditLimitSerializer",
    ),
    "StatementLineSerializer": (
        "credit.api.public.v1.serializers.credit",
        "StatementLineSerializer",
    ),
    "StatementListSerializer": (
        "credit.api.public.v1.serializers.credit",
        "StatementListSerializer",
    ),
    "StatementDetailSerializer": (
        "credit.api.public.v1.serializers.credit",
        "StatementDetailSerializer",
    ),
    "CloseStatementResponseSerializer": (
        "credit.api.public.v1.serializers.credit",
        "CloseStatementResponseSerializer",
    ),
    "LoanRiskOTPRequestSerializer": (
        "credit.api.public.v1.serializers.loan_risk",
        "LoanRiskOTPRequestSerializer",
    ),
    "LoanRiskOTPVerifySerializer": (
        "credit.api.public.v1.serializers.loan_risk",
        "LoanRiskOTPVerifySerializer",
    ),
    "LoanRiskReportSerializer": (
        "credit.api.public.v1.serializers.loan_risk",
        "LoanRiskReportSerializer",
    ),
    "LoanRiskReportDetailSerializer": (
        "credit.api.public.v1.serializers.loan_risk",
        "LoanRiskReportDetailSerializer",
    ),
    "LoanRiskReportListSerializer": (
        "credit.api.public.v1.serializers.loan_risk",
        "LoanRiskReportListSerializer",
    ),
}

if TYPE_CHECKING:
    from .credit import (
        CloseStatementResponseSerializer,
        CreditLimitSerializer,
        StatementDetailSerializer,
        StatementLineSerializer,
        StatementListSerializer,
    )
    from .loan_risk import (
        LoanRiskOTPRequestSerializer,
        LoanRiskOTPVerifySerializer,
        LoanRiskReportDetailSerializer,
        LoanRiskReportListSerializer,
        LoanRiskReportSerializer,
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
