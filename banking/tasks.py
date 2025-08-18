import logging
from datetime import timedelta

from celery import Task, shared_task
from celery.exceptions import Retry
from django.apps import apps
from django.db import transaction
from django.utils import timezone

from banking.utils.choices import BankCardStatus

logger = logging.getLogger(__name__)


class CardValidationTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        card_id = args[0] if args else kwargs.get("card_id")
        logger.error(
            f"Card validation for {card_id} has permanently failed after all "
            f"retries."
        )
        try:
            BankCard = apps.get_model("banking", "BankCard")  # lazy resolve
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
    try:
        BankCard = apps.get_model("banking", "BankCard")
        card = BankCard.objects.get(id=card_id)

        if card.status != BankCardStatus.PENDING:
            logger.info(
                f"Card {card_id} is no longer pending, skipping validation"
            )
            return True

        from banking.services.card_validator import validate_pending_card
        validate_pending_card(card_id)

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
            exc=exc, countdown=60 * (2 ** task_instance.request.retries)
        )


@shared_task(
    bind=True,
    base=CardValidationTask,
    max_retries=3,
    default_retry_delay=60,
)
def validate_card_task(self, card_id: str):
    return _validate_card_task_logic(self, card_id)


@shared_task
def reenqueue_stale_pending_cards(limit=200, older_than_minutes=1):
    BankCard = apps.get_model("banking", "BankCard")
    cutoff = timezone.localtime(timezone.now()) - timedelta(
        minutes=older_than_minutes
    )
    qs = (BankCard.objects
    .filter(
        status=BankCardStatus.PENDING, is_active=True, updated_at__lt=cutoff
    )
    .order_by("updated_at")
    .values_list("id", flat=True)[:limit])
    from banking.tasks import validate_card_task
    for card_id in qs:
        validate_card_task.delay(str(card_id))
