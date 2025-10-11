# profiles/tasks.py

import logging
import os
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from kyc.services.identity_auth_service import (
    IdentityAuthService,
    get_identity_auth_service,
)
from profiles.models import Profile
from profiles.models.kyc_attempt import (
    ProfileKYCAttempt,
    AttemptAlreadyProcessing,
)
from profiles.utils.choices import (
    KYCStatus, AttemptType, AttemptStatus,
    AuthenticationStage,
)

logger = logging.getLogger(__name__)


def _cleanup_temp_file(file_path: str) -> None:
    """Safely delete a temporary file if it exists."""
    if file_path and os.path.exists(file_path):
        try:
            os.unlink(file_path)
            logger.info(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")


# -----------------------------
# Helper to (re)queue Shahkar
# -----------------------------
def _should_queue_shahkar(
        profile: Profile, now: timezone.datetime, stale_after: timedelta
) -> bool:
    """
    Decide if Shahkar verification should be (re)queued for this profile.
    Rules:
      - must have national_id & phone_number
      - if status is ACCEPTED/REJECTED -> do not queue
      - if status is FAILED -> do not auto queue (needs user fix), except you want otherwise
      - if status is PROCESSING but stale (no update since 'stale_after') -> queue
      - if status is None -> queue if last attempt is stale or missing
    """
    if not profile.national_id or not profile.phone_number:
        return False

    status = profile.phone_national_id_match_status

    # Accepted or Rejected are terminal for Shahkar flow (no auto-retry)
    if status in (KYCStatus.ACCEPTED, KYCStatus.REJECTED):
        return False

    # Validation FAILED usually requires user correction; do not auto-enqueue
    if status == KYCStatus.FAILED:
        return False

    # For PROCESSING -> stale?
    if status == KYCStatus.PROCESSING:
        updated = profile.updated_at or profile.created_at
        return (now - updated) > stale_after

    # For None -> check attempt recency
    last_attempt = (
        ProfileKYCAttempt.objects
        .filter(profile=profile, attempt_type=AttemptType.SHAHKAR)
        .order_by("-created_at")
        .first()
    )
    if not last_attempt:
        return True

    # If last attempt is SUCCESS and we are None => shouldn't happen; skip
    if last_attempt.status == AttemptStatus.SUCCESS:
        return False

    # If last attempt FAILED/REJECTED recently, skip; else requeue
    return (now - last_attempt.created_at) > stale_after


def _enqueue_shahkar(profile_id: int) -> None:
    """Enqueue Shahkar verification task."""
    verify_identity_phone_national_id.apply_async((profile_id,), countdown=1)


@shared_task(bind=True)
def submit_profile_video_auth(
        self,
        profile_id: int,
        national_code: str,
        birth_date: str,
        selfie_video_path: str,
        rand_action: str,
        matching_thr: int | None = None,
        liveness_thr: int | None = None,
) -> dict:
    """
    Submit video authentication for a profile and persist tracking fields.
    Sets profile.auth_stage to VIDEO_VERIFIED and video_auth_status to PROCESSING.
    """
    try:
        attempt = ProfileKYCAttempt.start_new(
            profile_id=profile_id,
            attempt_type=AttemptType.VIDEO_SUBMIT,
            request_payload={
                "national_code": national_code,
                "birth_date": birth_date,
                "rand_action": rand_action,
                "matching_thr": matching_thr,
                "liveness_thr": liveness_thr,
            },
        )
    except AttemptAlreadyProcessing:
        _cleanup_temp_file(selfie_video_path)
        logger.warning(
            f"Profile {profile_id}: duplicate video submit while processing"
        )
        return {
            "success": False,
            "error": "kyc_in_progress",
            "message": "Video KYC already in progress for this profile.",
        }

    # Validate profile state under lock
    with transaction.atomic():
        try:
            profile = Profile.objects.select_for_update().get(id=profile_id)
        except Profile.DoesNotExist:
            _cleanup_temp_file(selfie_video_path)
            attempt.mark_failed("profile_not_found")
            return {"success": False, "error": "profile_not_found"}

        if not profile.can_submit_video_auth():
            _cleanup_temp_file(selfie_video_path)
            attempt.mark_failed("invalid_profile_state")
            logger.warning(
                f"Profile {profile_id} cannot submit video authentication. "
                f"Current stage: {profile.auth_stage}, expected: IDENTITY_VERIFIED"
            )
            return {
                "success": False,
                "error": "invalid_profile_state",
                "message": (
                    f"Profile is in {profile.auth_stage} stage. Must be in "
                    "IDENTITY_VERIFIED stage to submit video authentication."
                ),
            }

        if profile.is_video_auth_in_progress():
            _cleanup_temp_file(selfie_video_path)
            attempt.mark_failed("kyc_in_progress")
            logger.warning(
                f"Profile {profile_id} already has video authentication in progress (status: {profile.video_auth_status})."
            )
            return {
                "success": False,
                "error": "kyc_in_progress",
                "message": "Video authentication is already in progress for this profile.",
            }

        if profile.video_auth_status == KYCStatus.ACCEPTED:
            _cleanup_temp_file(selfie_video_path)
            attempt.mark_failed("already_accepted")
            logger.warning(
                f"Profile {profile_id} already has accepted video authentication status."
            )
            return {
                "success": False,
                "error": "already_accepted",
                "message": "Profile already has accepted video authentication status.",
            }

    # Call KYC service outside the transaction
    service: IdentityAuthService = get_identity_auth_service()
    try:
        result = service.verify_idcard_video(
            national_code=national_code,
            birth_date=birth_date,
            selfie_video_path=selfie_video_path,
            rand_action=rand_action,
            matching_thr=matching_thr,
            liveness_thr=liveness_thr,
        )
    except Exception as e:
        _cleanup_temp_file(selfie_video_path)
        # Retry on transient errors
        max_retries = getattr(settings, "KYC_VIDEO_SUBMIT_MAX_RETRIES", 3)
        retry_delay = getattr(settings, "KYC_VIDEO_SUBMIT_RETRY_DELAY", 60)
        attempt.bump_retry()
        if self.request.retries < max_retries:
            raise self.retry(exc=e, countdown=retry_delay)
        attempt.mark_failed(
            error_message=str(e),
            error_code="service_unavailable",
        )
        return {
            "success": False, "error": "service_unavailable", "message": str(e)
        }

    if not result.get("success"):
        _cleanup_temp_file(selfie_video_path)
        error_msg = result.get("error", "Unknown service error")
        attempt.mark_failed(error_msg, response_payload=result)
        logger.error(
            f"Video submit failed for profile {profile_id}: {error_msg}"
        )
        return {
            "success": False, "error": "service_error", "message": error_msg
        }

    # Extract uniqueId from the response structure
    data = (result or {}).get("data") or {}
    unique_id = data.get("uniqueId")
    if not unique_id:
        _cleanup_temp_file(selfie_video_path)
        attempt.mark_failed("missing_unique_id", response_payload=result)
        logger.error(
            f"Profile {profile_id}: No unique ID returned from KYC service"
        )
        return {
            "success": False,
            "error": "missing_unique_id",
            "message": "No unique ID returned from KYC service",
        }

    # Cleanup temp file on success too
    _cleanup_temp_file(selfie_video_path)

    # Save task id & schedule polling
    with transaction.atomic():
        try:
            profile = Profile.objects.select_for_update().get(id=profile_id)
            profile.mark_video_submitted(task_id=unique_id)
            transaction.on_commit(
                lambda: check_profile_video_auth_result.apply_async(
                    (profile_id,), countdown=30
                )
            )
            attempt.mark_success(
                response_payload=result, external_id=unique_id
            )
            logger.info(
                f"Profile {profile_id}: Video authentication submitted. Task ID: {unique_id}"
            )
        except ValidationError as e:
            attempt.mark_failed(
                error_message=str(e),
                error_code="validation_error",
            )
            logger.error(
                f"Profile {profile_id}: Validation error during submission: {e}"
            )
            return {
                "success": False, "error": "validation_error",
                "message": str(e)
            }
        except Profile.DoesNotExist:
            attempt.mark_failed("profile_not_found")
            return {"success": False, "error": "profile_not_found"}

    return {"success": True, "unique_id": unique_id}


@shared_task(bind=True)
def check_profile_video_auth_result(self, profile_id: int) -> dict:
    """
    Poll provider for video authentication result and update profile.
    Reschedules itself if result is not ready yet.
    """
    try:
        attempt = ProfileKYCAttempt.start_new(
            profile_id=profile_id,
            attempt_type=AttemptType.VIDEO_RESULT,
        )
    except AttemptAlreadyProcessing:
        return {"success": False, "error": "poll_in_progress"}

    # Lock and verify state
    with transaction.atomic():
        try:
            profile = Profile.objects.select_for_update().get(id=profile_id)
        except Profile.DoesNotExist:
            attempt.mark_failed("profile_not_found")
            return {"success": False, "error": "profile_not_found"}

        if not profile.is_video_auth_in_progress():
            attempt.mark_failed("invalid_profile_state")
            logger.warning(
                f"Profile {profile_id} invalid for result check: {profile.auth_stage}/{profile.video_auth_status}"
            )
            return {
                "success": False,
                "error": "invalid_profile_state",
                "message": (
                    f"Profile is in {profile.auth_stage}/{profile.video_auth_status} state. "
                    "Expected VIDEO_VERIFIED with PROCESSING."
                ),
            }

        if not profile.has_valid_video_task():
            attempt.mark_failed("missing_video_task_id")
            logger.error(f"Profile {profile_id} has no valid video task ID")
            return {"success": False, "error": "missing_video_task_id"}

        video_task_id = profile.video_task_id

    service: IdentityAuthService = get_identity_auth_service()
    try:
        result = service.get_video_verification_result(video_task_id)
    except Exception as e:
        max_retries = getattr(settings, "KYC_VIDEO_CHECK_MAX_RETRIES", 6)
        retry_delay = getattr(settings, "KYC_VIDEO_CHECK_RETRY_DELAY", 120)
        attempt.bump_retry()

        with transaction.atomic():
            try:
                profile = Profile.objects.select_for_update().get(
                    id=profile_id
                )
                profile.touch_video_auth_check()
            except Profile.DoesNotExist:
                pass

        if self.request.retries < max_retries:
            raise self.retry(exc=e, countdown=retry_delay)

        attempt.mark_failed(error_message=str(e), error_code="network_error")
        logger.error(f"Profile {profile_id}: Network error after max retries")
        return {"success": False, "error": "poll_timeout"}

    # Not-ready signals
    if not result.get("success") and result.get("status") in {
        404,
        "in_progress",
        "network"
    }:
        max_retries = getattr(settings, "KYC_VIDEO_CHECK_MAX_RETRIES", 6)
        retry_delay = getattr(settings, "KYC_VIDEO_CHECK_RETRY_DELAY", 120)
        attempt.bump_retry()
        with transaction.atomic():
            try:
                profile = Profile.objects.select_for_update().get(
                    id=profile_id
                )
                profile.touch_video_auth_check()
            except Profile.DoesNotExist:
                pass

        if self.request.retries < max_retries:
            logger.info(
                f"Profile {profile_id}: result not ready; retrying in {retry_delay}s"
            )
            raise self.retry(
                exc=Exception("result_not_ready"), countdown=retry_delay
            )

        attempt.mark_failed("max_retries_exceeded", response_payload=result)
        return {"success": False, "error": "poll_timeout"}

    # Other service errors
    if not result.get("success"):
        error_msg = result.get("error", "Unknown service error")
        with transaction.atomic():
            try:
                profile = Profile.objects.select_for_update().get(
                    id=profile_id
                )
                profile.update_video_auth_result(
                    accepted=False, error_details=str(error_msg)
                )
            except Profile.DoesNotExist:
                pass
        attempt.mark_failed(error_msg, response_payload=result)
        return {"success": False, "error": "service_error"}

    # Normalize payload: some providers nest in 'data'
    payload = result.get("data") if isinstance(
        result.get("data"), dict
    ) else result

    accepted = False
    try:
        verify_status = str(payload.get("verifyStatus", "")).upper()
        matching = str(payload.get("matching", "")).upper()
        liveness = str(payload.get("liveness", "")).upper()
        spoofing = str(payload.get("spoofing", "")).upper()

        if verify_status == "ACCEPT":
            accepted = True
        elif verify_status == "REJECT":
            accepted = False
        else:
            accepted = (matching == "TRUE") and (liveness == "TRUE") and (
                    spoofing == "FALSE")
    except Exception as e:
        accepted = False
        logger.warning(
            f"Profile {profile_id}: Could not determine result: {e}"
        )

    with transaction.atomic():
        try:
            profile = Profile.objects.select_for_update().get(id=profile_id)
            if profile.is_video_auth_in_progress():
                profile.update_video_auth_result(accepted=accepted)
        except Profile.DoesNotExist:
            pass

    attempt.mark_success(response_payload=payload)

    # Best-effort final status
    try:
        final_status = Profile.objects.get(id=profile_id).video_auth_status
    except Profile.DoesNotExist:
        final_status = None

    return {"success": True, "accepted": accepted, "status": final_status}


@shared_task(bind=True)
def reset_profile_video_auth(
        self, profile_id: int, reason: str = "manual_reset"
) -> dict:
    """
    Reset a profile's video authentication status back to identity verified stage.
    Useful for retry scenarios or manual intervention.
    """
    attempt = ProfileKYCAttempt.objects.create(
        profile_id=profile_id,
        attempt_type=AttemptType.VIDEO_RESULT,
        # reset is grouped here as well
    ).start(request_payload={"reason": reason})

    try:
        with transaction.atomic():
            profile = Profile.objects.select_for_update().get(id=profile_id)

            if not profile.can_retry_video_auth() and not profile.is_video_auth_in_progress():
                attempt.mark_failed("invalid_state_for_reset")
                logger.warning(
                    f"Profile {profile_id} cannot be reset. Current state: {profile.auth_stage}/{profile.video_auth_status}"
                )
                return {
                    "success": False,
                    "error": "invalid_state_for_reset",
                    "message": (
                        f"Profile is in {profile.auth_stage}/{profile.video_auth_status} state. Cannot reset."
                    ),
                }

            profile.reset_to_identity_verified()
    except Profile.DoesNotExist:
        attempt.mark_failed("profile_not_found")
        logger.warning(f"Profile {profile_id} not found for reset operation")
        return {"success": False, "error": "profile_not_found"}
    except ValidationError as e:
        attempt.mark_failed(
            error_message=str(e),
            error_code="validation_error",
        )
        logger.error(
            f"Validation error during reset for profile {profile_id}: {e}"
        )
        return {
            "success": False, "error": "validation_error", "message": str(e)
        }
    except Exception as e:
        attempt.mark_failed(
            error_message=str(e),
            error_code="reset_failed",
        )
        logger.error(
            f"Unexpected error during reset for profile {profile_id}: {e}"
        )
        return {"success": False, "error": "reset_failed", "message": str(e)}

    attempt.mark_success()
    logger.info(
        f"Profile {profile_id}: Video authentication reset to IDENTITY_VERIFIED stage. Reason: {reason}"
    )
    return {"success": True, "message": "Profile video authentication reset successfully"}


@shared_task(bind=True)
def verify_identity_phone_national_id(self, profile_id: int) -> dict:
    """
    Verify phone number and national ID matching using Shahkar API.
    Updates phone_national_id_match_status and auth_stage based on verification result.
    """
    try:
        attempt = ProfileKYCAttempt.start_new(
            profile_id=profile_id,
            attempt_type=AttemptType.SHAHKAR,
        )
    except AttemptAlreadyProcessing:
        logger.info(f"Profile {profile_id}: shahkar already in processing")
        return {"success": False, "error": "shahkar_in_progress"}

    try:
        profile = Profile.objects.get(id=profile_id)
    except Profile.DoesNotExist:
        attempt.mark_failed("profile_not_found")
        return {"success": False, "error": "profile_not_found"}

    if not profile.national_id or not profile.phone_number:
        attempt.mark_failed("missing_required_fields")
        logger.warning(
            f"Profile {profile_id}: Missing national_id or phone_number"
        )
        return {
            "success": False,
            "error": "missing_required_fields",
            "message": "National ID and phone number are required",
        }

    # Mark processing before calling provider
    with transaction.atomic():
        try:
            p = Profile.objects.select_for_update().get(id=profile_id)
            if p.phone_national_id_match_status in (KYCStatus.ACCEPTED,
                                                    KYCStatus.REJECTED):
                attempt.mark_failed("terminal_state")
                return {"success": False, "error": "terminal_state"}
            p.begin_phone_national_id_check()
        except Profile.DoesNotExist:
            attempt.mark_failed("profile_not_found")
            return {"success": False, "error": "profile_not_found"}

    service: IdentityAuthService = get_identity_auth_service()
    try:
        result = service.verify_mobile_national_id(
            national_code=profile.national_id,
            mobile_number=profile.phone_number,
        )
    except Exception as e:
        max_retries = getattr(settings, "KYC_SHAHKAR_MAX_RETRIES", 3)
        retry_delay = getattr(settings, "KYC_SHAHKAR_RETRY_DELAY", 60)
        attempt.bump_retry()
        if self.request.retries < max_retries:
            logger.warning(
                f"Profile {profile_id}: Shahkar API error, retrying: {e}"
            )
            raise self.retry(exc=e, countdown=retry_delay)

        logger.error(
            f"Profile {profile_id}: Shahkar API error after max retries: {e}"
        )
        try:
            with transaction.atomic():
                p = Profile.objects.select_for_update().get(id=profile_id)
                p.phone_national_id_match_status = None
                p.save(
                    update_fields=["phone_national_id_match_status",
                                   "updated_at"]
                )
        except Profile.DoesNotExist:
            pass
        attempt.mark_failed(
            error_message=str(e), error_code="service_unavailable"
        )
        return {"success": False, "error": "service_unavailable"}

    if not result.get("success"):
        error_msg = result.get("error", "Unknown service error")
        is_validation_error = result.get("is_validation_error", False)

        with transaction.atomic():
            try:
                p = Profile.objects.select_for_update().get(id=profile_id)
                if is_validation_error:
                    p.mark_phone_national_id_failed()
                else:
                    p.phone_national_id_match_status = None
                    p.save(
                        update_fields=["phone_national_id_match_status",
                                       "updated_at"]
                    )
            except Profile.DoesNotExist:
                pass

        attempt.mark_failed(
            error_message=error_msg,
            error_code="validation_error" if is_validation_error else "service_error",
            response_payload=result,
        )

        if is_validation_error:
            logger.warning(
                f"Profile {profile_id}: Shahkar validation error - {error_msg}"
            )
            return {
                "success": False,
                "error": "validation_error",
                "message": error_msg,
                "error_code": result.get("error_code"),
            }

        logger.error(
            f"Profile {profile_id}: Shahkar service error - {error_msg}"
        )
        return {
            "success": False, "error": "service_error", "message": error_msg
        }

    # Success path
    is_matched = result.get("is_matched", False)
    with transaction.atomic():
        try:
            p = Profile.objects.select_for_update().get(id=profile_id)
        except Profile.DoesNotExist:
            attempt.mark_failed("profile_not_found")
            return {"success": False, "error": "profile_not_found"}

        if is_matched:
            p.mark_identity_verified()
            attempt.mark_success(
                response_payload=result, external_id=result.get("unique_id")
            )
            logger.info(
                f"Profile {profile_id}: Phone/National ID verification successful"
            )
            return {
                "success": True,
                "is_matched": True,
                "message": "Identity verification completed successfully",
            }

        p.mark_phone_national_id_rejected()
        attempt.mark_rejected(
            response_payload=result, error_message="Not matched"
        )
        logger.warning(
            f"Profile {profile_id}: Phone/National ID verification failed - not matched"
        )
        return {
            "success": True,
            "is_matched": False,
            "message": "Phone number and national ID do not match",
        }


# ---------------------------------------------------
# Periodic watchdog to requeue stuck/missed Shahkar checks
# ---------------------------------------------------
@shared_task(bind=True)
def rehydrate_shahkar_checks(self) -> dict:
    """
    Periodic watchdog:
      - re-enqueue Shahkar verification for profiles that are stale or never attempted
      - ensures users don't get stuck due to transient/system failures
    """
    # Configurable staleness window (minutes)
    stale_minutes = int(getattr(settings, "KYC_SHAHKAR_STALE_MINUTES", 15))
    stale_after = timedelta(minutes=stale_minutes)
    now = timezone.now()

    qs = Profile.objects.filter(
        national_id__isnull=False,
        phone_number__isnull=False,
    ).exclude(
        phone_national_id_match_status=KYCStatus.ACCEPTED
    ).exclude(
        phone_national_id_match_status=KYCStatus.REJECTED
    )

    requeued = 0
    for profile in qs.iterator(chunk_size=500):
        try:
            if _should_queue_shahkar(profile, now, stale_after):
                _enqueue_shahkar(profile.id)
                requeued += 1
        except Exception as e:
            logger.warning(f"Watchdog skip profile {profile.id}: {e}")

    logger.info(f"Shahkar watchdog requeued={requeued}")
    return {"success": True, "requeued": requeued}


@shared_task(bind=True)
def rehydrate_video_auth_checks(self) -> dict:
    stale_minutes = int(getattr(settings, "KYC_VIDEO_STALE_MINUTES", 20))
    stale_after = timedelta(minutes=stale_minutes)
    now = timezone.now()

    qs = Profile.objects.filter(
        auth_stage=AuthenticationStage.IDENTITY_VERIFIED,
        video_auth_status=KYCStatus.PROCESSING,
    ).exclude(video_task_id__isnull=True).exclude(video_task_id__exact="")

    requeued = 0
    for p in qs.iterator(chunk_size=500):
        last = p.video_auth_last_checked_at or p.video_submitted_at or p.updated_at or p.created_at
        if (now - last) > stale_after:
            check_profile_video_auth_result.apply_async((p.id,), countdown=1)
            requeued += 1

    logger.info(f"Video watchdog requeued={requeued}")
    return {"success": True, "requeued": requeued}
