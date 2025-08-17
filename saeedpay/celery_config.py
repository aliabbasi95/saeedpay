"""
DEPRECATED: Celery configuration is centralized in `saeedpay/celery.py`.
This module is retained for reference only and is not imported by the app.
"""

# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# Task routing
CELERY_TASK_ROUTES = {
    'credit.tasks.statement_tasks.*': {'queue': 'statements'},
    'credit.tasks.credit_tasks.*': {'queue': 'credit'},
}

# Celery Beat schedule (alternative to celery.py)
CELERY_BEAT_SCHEDULE = {
    'daily-statement-maintenance': {
        'task': 'credit.tasks.statement_tasks.daily_statement_maintenance_task',
        'schedule': 86400.0,  # Daily
    },
    'month-end-processing': {
        'task': 'credit.tasks.statement_tasks.process_month_end_task',
        'schedule': 86400.0,  # Daily check
    },
    'process-pending-payments': {
        'task': 'credit.tasks.statement_tasks.process_pending_payments_task',
        'schedule': 86400.0,  # Daily
    },
    'daily-penalty-calculation': {
        'task': 'credit.tasks.statement_tasks.calculate_daily_penalties_task',
        'schedule': 86400.0,  # Daily
    },
}

# Celery settings
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Tehran'

# Task settings
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes

# Worker settings
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000
