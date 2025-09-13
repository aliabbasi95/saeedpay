#!/usr/bin/env bash
set -e
echo "Starting Celery beat..."
# If you use django-celery-beat scheduler:
exec celery -A saeedpay beat --loglevel=INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
# Otherwise (default scheduler):
# exec celery -A saeedpay beat --loglevel=INFO
