# credit/services/credit_limit_service.py
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from credit.models.credit_limit import CreditLimit
from credit.utils.choices import LoanRiskLevel
from profiles.utils.choices import AuthenticationStage

logger = logging.getLogger(__name__)


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


@transaction.atomic
def grant_or_upgrade_credit_limit(
        user,
        *,
        approved_limit: int,
        expiry_days: Optional[int] = None,
        grace_days: Optional[int] = None,
        activate: bool = True,
) -> dict:
    """
    Grant a NEW credit limit if the proposed approved_limit is STRICTLY HIGHER
    than the user's current active limit. Otherwise, reuse the existing one.

    This is intended for stage: VIDEO_VERIFIED + risk report completed.
    - Creates a fresh record on upgrade (so we keep audit/history).
    - Activates it atomically (previous actives should be auto-deactivated by model).
    - Idempotent w.r.t. concurrent calls: the second call will see the upgraded limit
      already active and will no-op.

    Returns:
        dict: {created(bool), upgraded(bool), limit_id(int|None), approved_limit(int), reason(str)}
    """
    amount = max(int(approved_limit), 0)
    if amount <= 0:
        return {
            "created": False,
            "upgraded": False,
            "limit_id": None,
            "approved_limit": 0,
            "reason": "non_positive_amount",
        }

    existing = CreditLimit.objects.get_user_credit_limit(user)

    # No active limit at all -> create like default path.
    if not existing:
        days = _resolve_expiry_days(expiry_days)
        expiry_date = timezone.localdate() + timedelta(days=days)
        grace = _resolve_grace_days(grace_days)
        limit = CreditLimit.objects.create(
            user=user,
            approved_limit=amount,
            is_active=False,
            expiry_date=expiry_date,
            grace_period_days=grace,
        )
        if activate:
            limit.activate()
        logger.info(
            "Granted credit limit (no existing) on risk report",
            extra={
                "user_id": user.pk,
                "approved_limit": amount,
                "expiry_date": str(expiry_date),
                "grace_days": grace,
            },
        )
        return {
            "created": True,
            "upgraded": False,
            "limit_id": limit.id,
            "approved_limit": amount,
            "reason": "granted_on_risk_report_no_existing",
        }

    # If proposed <= existing -> reuse (do not create duplicates).
    if amount <= int(existing.approved_limit):
        return {
            "created": False,
            "upgraded": False,
            "limit_id": existing.id,
            "approved_limit": int(existing.approved_limit),
            "reason": "existing_limit_is_equal_or_higher",
        }

    # Proposed is HIGHER -> create a NEW record and activate it.
    days = _resolve_expiry_days(expiry_days)
    expiry_date = timezone.localdate() + timedelta(days=days)
    grace = _resolve_grace_days(grace_days)

    new_limit = CreditLimit.objects.create(
        user=user,
        approved_limit=amount,
        is_active=False,
        expiry_date=expiry_date,
        grace_period_days=grace,
    )
    if activate:
        new_limit.activate()  # should atomically deactivate the previous active

    logger.info(
        "Upgraded credit limit on risk report",
        extra={
            "user_id": user.pk,
            "old_limit": int(existing.approved_limit),
            "new_limit": amount,
            "expiry_date": str(expiry_date),
            "grace_days": grace,
        },
    )
    return {
        "created": True,
        "upgraded": True,
        "limit_id": new_limit.id,
        "approved_limit": amount,
        "reason": "upgraded_on_risk_report",
    }


def resolve_limit_from_risk_level(risk_level: str) -> int:
    """
    Resolve approved credit limit amount from risk level using settings.
    Settings:
      CREDIT_LIMIT_BY_RISK_LEVEL = {"A1": 100_000_000, "A2": 80_000_000, "B1": 60_000_000, "B2": 40_000_000}
      CREDIT_LIMIT_FALLBACK = 0
    """
    mapping = getattr(settings, "CREDIT_LIMIT_BY_RISK_LEVEL", {}) or {}
    fallback = int(getattr(settings, "CREDIT_LIMIT_FALLBACK", 0))
    try:
        amount = int(mapping.get(str(risk_level), fallback))
    except Exception:
        amount = fallback
    return max(amount, 0)


def maybe_grant_credit_after_risk_report(*, profile, risk_level: str) -> dict:
    """
    After VIDEO_VERIFIED and receiving a risk report:
      - If risk is eligible, compute amount from settings.
      - If amount > current active limit -> create a NEW limit and activate it.
      - Else -> no-op (reuse existing).
    Idempotent across retries.
    """
    if profile.auth_stage != AuthenticationStage.VIDEO_VERIFIED:
        return {"granted": False, "reason": "auth_stage_not_video_verified"}

    eligible = {LoanRiskLevel.A1, LoanRiskLevel.A2, LoanRiskLevel.B1,
                LoanRiskLevel.B2}
    if risk_level not in eligible:
        return {"granted": False, "reason": "risk_level_not_eligible"}

    amount = resolve_limit_from_risk_level(risk_level)
    if amount <= 0:
        return {
            "granted": False,
            "reason": "resolved_amount_not_positive",
            "risk_level": risk_level,
        }

    def _grant():
        try:
            result = grant_or_upgrade_credit_limit(
                user=profile.user,
                approved_limit=amount,
                # Optional: allow per-policy overrides from settings for expiry/grace on risk-based limits
                expiry_days=getattr(settings, "CREDIT_RISK_EXPIRY_DAYS", None),
                grace_days=getattr(settings, "CREDIT_RISK_GRACE_DAYS", None),
            )
            logger.info(
                "credit.auto_grant | user_id=%s risk=%s amount=%s result=%s",
                profile.user_id, risk_level, amount, result.get("reason")
            )
        except Exception as e:
            logger.error(
                "credit.auto_grant.failed | user_id=%s risk=%s err=%s",
                profile.user_id, risk_level, e
            )

    transaction.on_commit(_grant)
    return {"granted": True, "risk_level": risk_level, "amount": amount}
