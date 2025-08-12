"""
Credit and BNPL settings configuration
"""
from django.conf import settings

# Credit Limit Settings
CREDIT_LIMIT_DEFAULT_EXPIRY_DAYS = getattr(settings, 'CREDIT_LIMIT_DEFAULT_EXPIRY_DAYS', 365)

# Statement Settings
STATEMENT_DUE_DAYS = getattr(settings, 'STATEMENT_DUE_DAYS', 5)
STATEMENT_PENALTY_RATE = getattr(settings, 'STATEMENT_PENALTY_RATE', 0.02)  # 2% per day
STATEMENT_MAX_PENALTY_RATE = getattr(settings, 'STATEMENT_MAX_PENALTY_RATE', 0.20)  # 20% max

# Payment Settings
PAYMENT_GRACE_PERIOD_DAYS = getattr(settings, 'PAYMENT_GRACE_PERIOD_DAYS', 3)

# Calendar Settings
USE_JALALI_CALENDAR = getattr(settings, 'USE_JALALI_CALENDAR', True)

# Reference Code Settings
REFERENCE_CODE_PREFIX = getattr(settings, 'REFERENCE_CODE_PREFIX', 'CR')
STATEMENT_REFERENCE_PREFIX = getattr(settings, 'STATEMENT_REFERENCE_PREFIX', 'ST')
