#!/usr/bin/env bash
set -e
: "${CELERY_CONCURRENCY:=4}"
: "${CELERY_QUEUES:=default}"

echo "Starting Celery worker..."
exec celery -A saeedpay worker --loglevel=INFO --concurrency=${CELERY_CONCURRENCY} -Q ${CELERY_QUEUES}
