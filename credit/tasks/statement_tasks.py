"""
Celery tasks for statement workflow automation
"""

from celery import shared_task
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from persiantools.jdatetime import JalaliDate
import logging

from credit.services.statement_service import (
    process_month_end_statements,
    process_pending_payments,
    calculate_daily_penalties,
    add_interest_to_current_statement,
    get_users_with_active_credit
)

logger = logging.getLogger(__name__)

User = get_user_model()


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def process_month_end_task(self):
    """
    Celery task to process month-end statement transitions
    Runs at the end of each Persian month
    """
    try:
        logger.info("Starting month-end statement processing task")
        
        # Check if it's the last day of the Persian month
        today = JalaliDate.today()
        next_day = today + timedelta(days=1)
        
        if next_day.month != today.month:
            result = process_month_end_statements()
            
            logger.info(
                f"Month-end processing completed: "
                f"{result['statements_closed']} statements closed, "
                f"{result['statements_created']} statements created"
            )
            
            return {
                'status': 'success',
                'result': result
            }
        else:
            logger.info("Not last day of Persian month, skipping month-end processing")
            return {
                'status': 'skipped',
                'message': 'Not last day of Persian month'
            }
            
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
        
        return {
            'status': 'success',
            'result': result
        }
        
    except Exception as e:
        logger.error(f"Error in pending payments task: {str(e)}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def calculate_daily_penalties_task(self):
    """
    Celery task to calculate daily penalties for overdue statements
    Runs daily
    """
    try:
        logger.info("Starting daily penalty calculation task")
        
        result = calculate_daily_penalties()
        
        logger.info(
            f"Daily penalty calculation completed: "
            f"{result['statements_processed']} penalties applied"
        )
        
        return {
            'status': 'success',
            'result': result
        }
        
    except Exception as e:
        logger.error(f"Error in daily penalties task: {str(e)}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def add_interest_to_all_users_task(self):
    """
    Celery task to add interest to all users' current statements
    Runs at the beginning of each Persian month
    """
    try:
        logger.info("Starting interest addition task for all users")
        
        users = get_users_with_active_credit()
        added_count = 0
        errors = []
        
        for user in users:
            try:
                from credit.services.statement_service import add_interest_to_current_statement
                if add_interest_to_current_statement(user):
                    added_count += 1
                    
            except Exception as e:
                error_msg = f"Error adding interest for user {user.id}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        logger.info(
            f"Interest addition completed: {added_count} users processed, "
            f"{len(errors)} errors"
        )
        
        return {
            'status': 'success',
            'users_processed': len(users),
            'interest_added': added_count,
            'errors': errors
        }
        
    except Exception as e:
        logger.error(f"Error in interest addition task: {str(e)}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def process_user_statement_task(self, user_id: int, year: int, month: int):
    """
    Celery task to process a specific user's statement
    """
    try:
        user = User.objects.get(id=user_id)
        
        from credit.services.statement_service import get_statement_summary
        summary = get_statement_summary(user, year, month)
        
        if not summary:
            return {
                'status': 'error',
                'message': f'Statement not found for user {user_id}, {year}/{month}'
            }
        
        return {
            'status': 'success',
            'statement_summary': summary
        }
        
    except User.DoesNotExist:
        return {
            'status': 'error',
            'message': f'User {user_id} not found'
        }
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
        old_statements = Statement.objects.filter(
            created_at__lt=cutoff_date
        ).count()
        
        logger.info(
            f"Old statements cleanup check: {old_statements} statements older than {days_old} days"
        )
        
        return {
            'status': 'success',
            'old_statements_count': old_statements,
            'message': 'Cleanup check completed - no data deleted for audit purposes'
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
        
        # Run daily penalties
        penalty_result = calculate_daily_penalties_task.apply_async()
        results['daily_penalties'] = penalty_result.get()
        
        # Run pending payments
        payments_result = process_pending_payments_task.apply_async()
        results['pending_payments'] = payments_result.get()
        
        logger.info("Daily statement maintenance completed")
        
        return {
            'status': 'success',
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Error in daily maintenance task: {str(e)}")
        raise self.retry(exc=e)
