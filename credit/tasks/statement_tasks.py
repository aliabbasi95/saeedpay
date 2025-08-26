"""
Celery tasks for statement workflow automation
"""

from celery import shared_task
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

from credit.services.statement_service import (
    process_month_end_statements,
    process_pending_payments,
)
from credit.services.statement_service import get_statement_summary
from credit.models.statement import Statement

logger = logging.getLogger(__name__)

User = get_user_model()


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def process_month_end_task(self):
    """
    Celery task to process month-end statement transitions
    Runs at the first hour of each Persian month
    """
    try:
        logger.info("Starting month-end statement processing task")

        # Check if it's the first hour of the current month
        now = datetime.now()
        is_first_hour = now.day == 1 and now.hour == 0

        if is_first_hour:
            result = process_month_end_statements()

            logger.info(
                f"Month-end processing completed: "
                f"{result['statements_closed']} statements closed, "
                f"{result['statements_created']} statements created"
            )

            return {"status": "success", "result": result}
        else:
            logger.info("Not the first hour of the month, skipping month-end processing")
            return {"status": "skipped", "message": "Not the first hour of the month"}

    except Exception as e:
        logger.error(f"Error in month-end task: {str(e)}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def process_pending_payments_task(self):
    """
    Celery task to process pending payments after grace period
    Runs daily to check and process expired grace periods
    """
    try:
        logger.info("Starting pending payments processing task")

        result = process_pending_payments()

        logger.info(
            f"Pending payments processing completed: "
            f"{result['statements_processed']} statements processed"
        )

        return {"status": "success", "result": result}

    except Exception as e:
        logger.error(f"Error in pending payments task: {str(e)}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def process_user_statement_task(self, user_id: int, year: int, month: int):
    """
    Celery task to process a specific user's statement
    """
    try:
        user = User.objects.get(id=user_id)

        summary = get_statement_summary(user, year, month)

        if not summary:
            return {
                "status": "error",
                "message": f"Statement not found for user {user_id}, {year}/{month}",
            }

        return {"status": "success", "statement_summary": summary}

    except User.DoesNotExist:
        return {"status": "error", "message": f"User {user_id} not found"}
    except Exception as e:
        logger.error(f"Error processing user statement task: {str(e)}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def cleanup_old_statements_task(self, days_old: int = 365):
    """
    Celery task to cleanup old statements and related data
    """
    try:
        logger.info("Starting old statements cleanup task")

        cutoff_date = timezone.now() - timedelta(days=days_old)

        # Get old statements (keep for audit purposes, just log)
        old_statements = Statement.objects.filter(created_at__lt=cutoff_date).count()

        logger.info(
            f"Old statements cleanup check: {old_statements} statements older than "
            f"{days_old} days"
        )

        return {
            "status": "success",
            "old_statements_count": old_statements,
            "message": "Cleanup check completed - no data deleted for audit purposes",
        }

    except Exception as e:
        logger.error(f"Error in cleanup task: {str(e)}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=5, default_retry_delay=600)
def daily_statement_maintenance_task(self):
    """
    Daily maintenance task for statement workflow
    Runs all daily maintenance operations
    """
    try:
        logger.info("Starting daily statement maintenance")

        results = {}

        # Run pending payments
        payments_result = process_pending_payments_task.apply_async()

        # Wait for both tasks to complete
        results["pending_payments"] = payments_result.get(timeout=300)

        logger.info("Daily statement maintenance completed")

        return {"status": "success", "results": results}

    except Exception as e:
        logger.error(f"Error in daily maintenance task: {str(e)}")
        raise self.retry(exc=e)
