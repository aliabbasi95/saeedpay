# banking/tasks.py

import logging
from celery import Task, shared_task
from celery.exceptions import Retry
from django.db import transaction

from banking.models import BankCard
from banking.services.card_validator import validate_pending_card
from banking.utils.choices import BankCardStatus

logger = logging.getLogger(__name__)


class CardValidationTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Custom failure handler to mark the card as rejected
        after all retries have been exhausted.
        """
        card_id = args[0]
        logger.error(
            f"Card validation for {card_id} has permanently failed after all "
            f"retries."
        )
        try:
            with transaction.atomic():
                card = BankCard.objects.select_for_update().get(id=card_id)
                if card.status == BankCardStatus.PENDING:
                    card.status = BankCardStatus.REJECTED
                    card.rejection_reason = (
                        "خطا در سیستم تایید کارت. لطفاً مجدداً تلاش کنید."
                    )
                    card.save(update_fields=["status", "rejection_reason"])
                    logger.info(
                        f"Card {card_id} marked as REJECTED due to validation "
                        f"system failure."
                    )
        except BankCard.DoesNotExist:
            logger.error(
                f"Card {card_id} not found while attempting to mark as "
                f"rejected."
            )
        except Exception as e:
            logger.error(
                f"Failed to mark card {card_id} as rejected: {str(e)}"
            )


def _validate_card_task_logic(task_instance, card_id: str):
    """
    Core logic for the validation task. Extracted for easier testing.
    """
    try:
        logger.info(f"Starting card validation logic for card {card_id}")
        card = BankCard.objects.get(id=card_id)

        if card.status != BankCardStatus.PENDING:
            logger.info(
                f"Card {card_id} is no longer pending, skipping validation"
            )
            return True

        validate_pending_card(card)
        logger.info(
            f"Card validation logic completed successfully for card {card_id}"
        )
        return True

    except BankCard.DoesNotExist:
        logger.error(f"Card {card_id} not found during validation task logic")
        return False

    except Exception as exc:
        if isinstance(exc, Retry):
            raise

        logger.warning(
            f"Card validation failed for card {card_id}. Retrying... "
            f"(Attempt {task_instance.request.retries + 1}/"
            f"{task_instance.max_retries})"
        )
        raise task_instance.retry(
            exc=exc, countdown=60 * (2**task_instance.request.retries)
        )


@shared_task(
    bind=True,
    base=CardValidationTask,
    max_retries=3,
    default_retry_delay=60,
)
def validate_card_task(self, card_id: str):
    """
    Celery task to validate a bank card. Wraps the core logic for execution by
    a worker.
    """
    return _validate_card_task_logic(self, card_id)
