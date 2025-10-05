# credit/services/credit_limit_service.py
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from credit.models.credit_limit import CreditLimit

logger = logging.getLogger(__name__)


# Settings keys (override as needed in settings.py):
# CREDIT_DEFAULT_APPROVED_LIMIT: int (e.g., 1_000_000)
# CREDIT_DEFAULT_EXPIRY_DAYS: int (e.g., 365)
# CREDIT_DEFAULT_GRACE_DAYS: Optional[int] (None = use system default)


def _resolve_default_limit(approved_limit: Optional[int]) -> int:
    """Resolve approved limit from argument or settings."""
    if approved_limit is not None:
        return max(int(approved_limit), 0)
    return max(int(getattr(settings, "CREDIT_DEFAULT_APPROVED_LIMIT", 0)), 0)


def _resolve_expiry_days(expiry_days: Optional[int]) -> int:
    """Resolve expiry days from argument or settings (min=1)."""
    if expiry_days is not None:
        return max(int(expiry_days), 1)
    return max(int(getattr(settings, "CREDIT_DEFAULT_EXPIRY_DAYS", 365)), 1)


def _resolve_grace_days(grace_days: Optional[int]) -> Optional[int]:
    """Resolve grace days; None means use system default per model logic."""
    if grace_days is None:
        return getattr(settings, "CREDIT_DEFAULT_GRACE_DAYS", None)
    return max(int(grace_days), 1)


@transaction.atomic
def grant_default_credit_limit(
        user,
        *,
        approved_limit: Optional[int] = None,
        expiry_days: Optional[int] = None,
        grace_days: Optional[int] = None,
        activate: bool = True,
) -> dict:
    """
    Create (or reuse) an active credit limit for the given user.
    Idempotent: if an active (non-expired) limit exists, it will be reused.

    Returns a summary dict for observability and tests.
    """
    # If user already has an active non-expired limit, reuse it.
    existing = CreditLimit.objects.get_user_credit_limit(user)
    if existing:
        return {
            "created": False,
            "limit_id": existing.id,
            "approved_limit": int(existing.approved_limit),
            "reason": "already_has_active_limit",
        }

    limit_value = _resolve_default_limit(approved_limit)
    if limit_value <= 0:
        logger.info("Default credit limit is disabled (<= 0). Skipping grant.")
        return {
            "created": False,
            "limit_id": None,
            "approved_limit": 0,
            "reason": "disabled",
        }

    days = _resolve_expiry_days(expiry_days)
    expiry_date = timezone.localdate() + timedelta(days=days)
    grace = _resolve_grace_days(grace_days)

    # Build the new limit (initially inactive to let .activate() handle exclusivity)
    limit = CreditLimit.objects.create(
        user=user,
        approved_limit=limit_value,
        is_active=False,
        expiry_date=expiry_date,
        grace_period_days=grace,
    )

    # Activate atomically (deactivates previous actives per model method)
    if activate:
        limit.activate()

    logger.info(
        "Granted default credit limit",
        extra={
            "user_id": user.pk,
            "approved_limit": limit_value,
            "expiry_date": str(expiry_date),
            "grace_days": grace,
        },
    )
    return {
        "created": True,
        "limit_id": limit.id,
        "approved_limit": limit_value,
        "reason": "auto_granted_on_identity_verified",
    }
