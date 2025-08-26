"""
Credit and BNPL constants configuration
"""
from django.conf import settings

# Credit Limit Settings
CREDIT_LIMIT_DEFAULT_EXPIRY_DAYS = getattr(settings, 'CREDIT_LIMIT_DEFAULT_EXPIRY_DAYS', 365)

# Statement Settings
STATEMENT_GRACE_DAYS = getattr(settings, 'STATEMENT_GRACE_DAYS', 5)
STATEMENT_PENALTY_RATE = getattr(settings, 'CREDIT_STATEMENT_PENALTY_RATE', 0.02)  # 2% per day
STATEMENT_MAX_PENALTY_RATE = getattr(settings, 'CREDIT_STATEMENT_MAX_PENALTY_RATE', 0.20)  # 20% max

# Minimum Payment Settings
MINIMUM_PAYMENT_PERCENTAGE = getattr(settings, 'MINIMUM_PAYMENT_PERCENTAGE', 0.10)  # 10% minimum
MINIMUM_PAYMENT_THRESHOLD = getattr(settings, 'MINIMUM_PAYMENT_THRESHOLD', 100000)  # 100,000 Rials threshold

# Payment Settings
PAYMENT_GRACE_PERIOD_DAYS = getattr(settings, 'PAYMENT_GRACE_PERIOD_DAYS', 3)

# Interest Settings
MONTHLY_INTEREST_RATE = getattr(settings, 'MONTHLY_INTEREST_RATE', 0.02)  # 2% monthly interest

# Calendar Settings
USE_JALALI_CALENDAR = getattr(settings, 'USE_JALALI_CALENDAR', True)

# Reference Code Settings
REFERENCE_CODE_PREFIX = getattr(settings, 'REFERENCE_CODE_PREFIX', 'CR')
STATEMENT_REFERENCE_PREFIX = getattr(settings, 'STATEMENT_REFERENCE_PREFIX', 'ST')
