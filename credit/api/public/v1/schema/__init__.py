# credit/api/public/v1/schema/__init__.py

from .credit_limit import credit_limit_viewset_schema

from .statement import (
    statement_viewset_schema,
    add_purchase_schema,
    add_payment_schema,
    close_current_schema,
)
from .statement_line import statement_line_viewset_schema

from .loan_risk import (
    loan_risk_otp_request_schema,
    loan_risk_otp_verify_schema,
    loan_risk_report_check_schema,
    loan_risk_report_detail_schema,
    loan_risk_report_list_schema,
    loan_risk_report_latest_schema,
)
