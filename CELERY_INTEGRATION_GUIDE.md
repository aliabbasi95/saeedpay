# Celery Integration Guide for Statement Workflow

## Overview

This guide explains how to set up and use Celery for automating the statement workflow in the credit system.

## Installation

### 1. Install Required Packages

```bash
pip install celery redis django-celery-beat persiantools
```

### 2. Install Redis (if not already installed)

```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Start Redis
redis-server
```

## Configuration

### 1. Update Django Settings

Add the following to your `settings.py`:

```python
# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# Celery Beat Schedule
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'daily-statement-maintenance': {
        'task': 'credit.tasks.statement_tasks.daily_statement_maintenance_task',
        'schedule': crontab(hour=2, minute=0),
    },
    'month-end-processing': {
        'task': 'credit.tasks.statement_tasks.process_month_end_task',
        'schedule': crontab(hour=23, minute=30),
    },
    'process-pending-payments': {
        'task': 'credit.tasks.statement_tasks.process_pending_payments_task',
        'schedule': crontab(hour=6, minute=0),
    },
    'daily-penalty-calculation': {
        'task': 'credit.tasks.statement_tasks.calculate_daily_penalties_task',
        'schedule': crontab(hour=1, minute=0),
    },
    'add-interest-to-statements': {
        'task': 'credit.tasks.statement_tasks.add_interest_to_all_users_task',
        'schedule': crontab(hour=0, minute=30, day_of_month=1),
    },
}

# Timezone settings
CELERY_TIMEZONE = 'Asia/Tehran'
```

### 2. Update __init__.py

Add to your project's `__init__.py`:

```python
from .celery import app as celery_app

__all__ = ('celery_app',)
```

## Running Celery

### 1. Start Celery Worker

```bash
celery -A saeedpay worker -l info
```

### 2. Start Celery Beat (Scheduler)

```bash
celery -A saeedpay beat -l info
```

### 3. Run with Multiple Queues

```bash
# Start worker for statements queue
celery -A saeedpay worker -Q statements -l info

# Start worker for credit queue
celery -A saeedpay worker -Q credit -l info

# Start beat scheduler
celery -A saeedpay beat -l info
```

## Testing

### Test Individual Tasks

```bash
# Test month-end processing
python manage.py test_celery_tasks --task month_end

# Test pending payments
python manage.py test_celery_tasks --task pending_payments

# Test daily penalties
python manage.py test_celery_tasks --task daily_penalties

# Test all tasks
python manage.py test_celery_tasks --task all

# Run asynchronously
python manage.py test_celery_tasks --task all --async
```

### Monitor Tasks

```bash
# Flower monitoring (install with: pip install flower)
celery -A saeedpay flower --port=5555
```

## Task Schedule

| Task | Frequency | Time | Purpose |
|------|-----------|------|---------|
| `daily_statement_maintenance_task` | Daily | 2:00 AM | Run daily maintenance |
| `process_month_end_task` | Daily | 11:30 PM | Check for month-end |
| `process_pending_payments_task` | Daily | 6:00 AM | Process grace period payments |
| `calculate_daily_penalties_task` | Daily | 1:00 AM | Calculate overdue penalties |
| `add_interest_to_all_users_task` | Monthly | 12:30 AM (1st) | Add interest to new statements |

## Service Functions

The following service functions are available for use in Celery tasks:

### Statement Service Functions

- `process_month_end_statements()` - Process month-end transitions
- `process_pending_payments()` - Process pending payments after grace period
- `calculate_daily_penalties()` - Calculate penalties for overdue statements
- `add_interest_to_current_statement(user)` - Add interest to user's current statement
- `get_statement_summary(user, year, month)` - Get statement summary
- `process_user_payment(user, amount, transaction_id)` - Process user payment

### Persian Calendar Utilities

- `is_last_day_of_persian_month()` - Check if today is last day of month
- `get_persian_month_days(year, month)` - Get days in Persian month
- `get_business_days_until_month_end()` - Get business days until month end

## Error Handling

All Celery tasks include:

- Automatic retry with exponential backoff
- Comprehensive logging
- Error tracking and reporting
- Task expiration to prevent stale execution

## Monitoring

### Logs

- All tasks log to the `credit.tasks` logger
- Check logs for detailed execution information

### Metrics

- Task success/failure rates
- Processing times
- Error counts

## Troubleshooting

### Common Issues

1. _**Redis Connection Error**_
   - Ensure Redis is running: `redis-cli ping`
   - Check Redis configuration in settings

2. _**Task Not Executing**_
   - Verify Celery worker is running
   - Check task routing configuration
   - Review task schedules in beat

3. _**Timezone Issues**_
   - Ensure `CELERY_TIMEZONE` matches your local timezone
   - Use `Asia/Tehran` for Persian calendar

4. _**Memory Issues**_
   - Monitor worker memory usage
   - Adjust `worker_max_tasks_per_child` if needed

### Debug Mode

```bash
# Run with debug logging
celery -A saeedpay worker -l debug

# Run single task manually
celery -A saeedpay call credit.tasks.statement_tasks.daily_statement_maintenance_task
```
