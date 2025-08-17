"""
Celery configuration for statement workflow automation
"""

from saeedpay.celery import app  # Centralized Celery app; configs/schedules live in saeedpay/celery.py

# Statement workflow scheduling
"""Beat schedule moved to saeedpay/celery.py"""

"""Additional Celery configuration moved to saeedpay/celery.py"""
