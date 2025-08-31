# credit/tasks.py

from celery import shared_task

from credit.services.use_cases import StatementUseCases


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def task_month_end_rollover(self):
    """
    Close CURRENT statements of past Persian months, create new CURRENT with carry-over,
    and add monthly interest on negative carry-over.
    Safe to run periodically; only affects statements that belong to past months.
    """
    try:
        result = StatementUseCases.perform_month_end_rollover()
        # result: {"statements_closed": int, "statements_created": int, "interest_lines_added": int}
        return {"status": "success", "result": result}
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def task_finalize_due_windows(self):
    """
    Finalize all PENDING_PAYMENT statements whose due_date has passed:
    - Read payments on CURRENT during each pending statement's due window.
    - Decide outcome (closed_no_penalty / closed_with_penalty).
    - Apply penalty line to CURRENT when needed.
    """
    try:
        result = StatementUseCases.finalize_due_windows()
        # result: FinalizeResult dataclass -> we return a dict for serialization
        return {
            "status": "success",
            "result": {
                "finalized_count": result.finalized_count,
                "closed_without_penalty_count": result.closed_without_penalty_count,
                "closed_with_penalty_count": result.closed_with_penalty_count,
            },
        }
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def task_daily_credit_maintenance(self):
    """
    Convenience wrapper to run both periodic routines in sequence.
    It is safe and idempotent: month_end_rollover only acts on past-month CURRENTs,
    finalize_due_windows only acts on pending statements past due_date.
    """
    try:
        rollover = task_month_end_rollover.apply().result
        finalize = task_finalize_due_windows.apply().result
        return {
            "status": "success",
            "month_end_rollover": rollover,
            "finalize_due_windows": finalize,
        }
    except Exception as exc:
        raise self.retry(exc=exc)
