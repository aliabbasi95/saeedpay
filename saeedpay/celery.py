# saeedpay/celery.py
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saeedpay.settings')

# Create Celery app - broker URL will be configured from Django settings
app = Celery('saeedpay')

# Load configuration from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all Django apps
app.autodiscover_tasks()

# Consolidated Celery configuration (merged from settings.py, credit/celery.py, and celery_config.py)
# Baseline serializers, timezone, and worker tuning
app.conf.update(
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/0',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Tehran',  # Persian timezone
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,       # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    task_always_eager=False,
    task_default_queue='ariansupply',
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Task routing for credit domain
app.conf.task_routes = {
    'credit.tasks.statement_tasks.*': {'queue': 'statements'},
    'credit.tasks.credit_tasks.*': {'queue': 'credit'},
}

# Merge Celery Beat schedules defined in Django settings with credit schedules
# Note: Any schedules already provided via CELERY_BEAT_SCHEDULE in settings.py are preserved.
app.conf.beat_schedule = getattr(app.conf, 'beat_schedule', {}) or {}

app.conf.beat_schedule.update({
    # Wallet schedules moved from settings.py
    'expire-pending-payment-requests-every-minute': {
        'task': 'wallets.tasks.task_expire_pending_payment_requests',
        'schedule': crontab(minute='*/1'),
    },
    'cleanup-cancelled-and-expired-requests-every-hour': {
        'task': 'wallets.tasks.task_cleanup_cancelled_and_expired_requests',
        'schedule': crontab(minute=0, hour='*/1'),
    },
    'expire-pending-transfer-every-minute': {
        'task': 'wallets.tasks.task_expire_pending_transfer_requests',
        'schedule': crontab(minute='*/1'),
    },

    # Daily maintenance task - runs every day at 2 AM
    'daily-statement-maintenance': {
        'task': 'credit.tasks.statement_tasks.daily_statement_maintenance_task',
        'schedule': crontab(hour=2, minute=0),
        'options': {'expires': 3600},  # Task expires after 1 hour
    },

    # Month-end processing - runs on the last day of each Persian month at 11:30 PM
    'month-end-processing': {
        'task': 'credit.tasks.statement_tasks.process_month_end_task',
        'schedule': crontab(hour=23, minute=30),
        'options': {'expires': 3600},
    },

    # Pending payments processing - runs daily at 6 AM
    'process-pending-payments': {
        'task': 'credit.tasks.statement_tasks.process_pending_payments_task',
        'schedule': crontab(hour=6, minute=0),
        'options': {'expires': 3600},
    },

    # Daily penalty calculation - runs daily at 1 AM
    'daily-penalty-calculation': {
        'task': 'credit.tasks.statement_tasks.calculate_daily_penalties_task',
        'schedule': crontab(hour=1, minute=0),
        'options': {'expires': 3600},
    },

    # Interest addition for new month - runs on the 1st of each Persian month at 12:30 AM
    'add-interest-to-statements': {
        'task': 'credit.tasks.statement_tasks.add_interest_to_all_users_task',
        'schedule': crontab(hour=0, minute=30, day_of_month=1),
        'options': {'expires': 3600},
    },

    # Weekly cleanup check - runs every Sunday at 3 AM
    'weekly-cleanup-check': {
        'task': 'credit.tasks.statement_tasks.cleanup_old_statements_task',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),
        'args': [365],  # Check statements older than 365 days
        'options': {'expires': 3600},
    },
})
