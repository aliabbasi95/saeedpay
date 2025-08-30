# credit/utils/constants.py
from django.conf import settings

# Credit Limit
CREDIT_LIMIT_DEFAULT_EXPIRY_DAYS = getattr(
    settings, 'CREDIT_LIMIT_DEFAULT_EXPIRY_DAYS', 365
)

# Statement Settings
STATEMENT_GRACE_DAYS = getattr(settings, 'STATEMENT_GRACE_DAYS', 25)
STATEMENT_PENALTY_RATE = getattr(settings, 'CREDIT_STATEMENT_PENALTY_RATE', 0.02)  # 2% per day
STATEMENT_MAX_PENALTY_RATE = getattr(settings, 'CREDIT_STATEMENT_MAX_PENALTY_RATE', 0.20)  # 20% max

# Penalty
LATE_FEE_FIXED = getattr(settings, 'LATE_FEE_FIXED', 100_000)
LATE_FEE_CAP = getattr(settings, 'LATE_FEE_CAP', 300_000)

# حداقل پرداخت
MINIMUM_PAYMENT_PERCENTAGE = getattr(
    settings, 'MINIMUM_PAYMENT_PERCENTAGE', 0.10
)
MINIMUM_PAYMENT_THRESHOLD = getattr(
    settings, 'MINIMUM_PAYMENT_THRESHOLD', 100_000
)

# Calendar / Refs
USE_JALALI_CALENDAR = getattr(settings, 'USE_JALALI_CALENDAR', True)
REFERENCE_CODE_PREFIX = getattr(settings, 'REFERENCE_CODE_PREFIX', 'CR')
STATEMENT_REFERENCE_PREFIX = getattr(
    settings, 'STATEMENT_REFERENCE_PREFIX', 'ST'
)

MONTHLY_INTEREST_RATE = getattr(settings, 'MONTHLY_INTEREST_RATE', 0.02)
