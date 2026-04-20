# credit/admin/__init__.py

from .credit_limit import CreditLimitAdmin
from .loan_risk_report import LoanRiskReportAdmin
from .statement import StatementAdmin
from .statement_line import StatementLineAdmin

__all__ = [
    "CreditLimitAdmin",
    "LoanRiskReportAdmin",
    "StatementAdmin",
    "StatementLineAdmin",
]
