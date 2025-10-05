# profiles/tasks.py

import logging
import os

from celery import shared_task
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from kyc.services.identity_auth_service import (
    IdentityAuthService,
    get_identity_auth_service,
)
from profiles.models import Profile
from profiles.utils.choices import KYCStatus

logger = logging.getLogger(__name__)


def _cleanup_temp_file(file_path: str) -> None:
    """Safely delete a temporary file if it exists."""
    if file_path and os.path.exists(file_path):
        try:
            os.unlink(file_path)
            logger.info(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")


@shared_task(bind=True)
def submit_profile_video_kyc(
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
    Submit video KYC for a profile and persist tracking fields.
    Sets profile.auth_stage to VIDEO_VERIFIED and kyc_status to PROCESSING.
    """
    # Validate profile state under lock
    with transaction.atomic():
        try:
            profile = Profile.objects.select_for_update().get(id=profile_id)
        except Profile.DoesNotExist:
            _cleanup_temp_file(selfie_video_path)
            return {"success": False, "error": "profile_not_found"}

        if not profile.can_submit_video_kyc():
            _cleanup_temp_file(selfie_video_path)
            logger.warning(
                f"Profile {profile_id} cannot submit video KYC. "
                f"Current stage: {profile.auth_stage}, expected: IDENTITY_VERIFIED"
            )
            return {
                "success": False,
                "error": "invalid_profile_state",
                "message": (
                    f"Profile is in {profile.auth_stage} stage. Must be in "
                    "IDENTITY_VERIFIED stage to submit video KYC."
                ),
            }

        if profile.is_video_kyc_in_progress():
            _cleanup_temp_file(selfie_video_path)
            logger.warning(
                f"Profile {profile_id} already has video KYC in progress "
                f"(status: {profile.kyc_status})."
            )
            return {
                "success": False,
                "error": "kyc_in_progress",
                "message": "Video KYC is already in progress for this profile.",
            }

        if profile.kyc_status == KYCStatus.ACCEPTED:
            _cleanup_temp_file(selfie_video_path)
            logger.warning(
                f"Profile {profile_id} already has accepted KYC status."
            )
            return {
                "success": False,
                "error": "already_accepted",
                "message": "Profile already has accepted KYC status.",
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
        if self.request.retries < max_retries:
            raise self.retry(exc=e, countdown=retry_delay)
        return {
            "success": False, "error": "service_unavailable", "message": str(e)
        }

    if not result.get("success"):
        _cleanup_temp_file(selfie_video_path)
        error_msg = result.get("error", "Unknown service error")
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
                lambda: check_profile_video_kyc_result.apply_async(
                    (profile_id,), countdown=30
                )
            )
            logger.info(
                f"Profile {profile_id}: Video KYC submitted. Task ID: {unique_id}"
            )
        except ValidationError as e:
            logger.error(
                f"Profile {profile_id}: Validation error during submission: {e}"
            )
            return {
                "success": False, "error": "validation_error",
                "message": str(e)
            }
        except Profile.DoesNotExist:
            # Rare race condition
            return {"success": False, "error": "profile_not_found"}

    return {"success": True, "unique_id": unique_id}


@shared_task(bind=True)
def check_profile_video_kyc_result(self, profile_id: int) -> dict:
    """
    Poll provider for video KYC result and update profile.
    Reschedules itself if result is not ready yet.
    """
    # Lock and verify state
    with transaction.atomic():
        try:
            profile = Profile.objects.select_for_update().get(id=profile_id)
        except Profile.DoesNotExist:
            return {"success": False, "error": "profile_not_found"}

        if not profile.is_video_kyc_in_progress():
            logger.warning(
                f"Profile {profile_id} invalid for result check: "
                f"{profile.auth_stage}/{profile.kyc_status}"
            )
            return {
                "success": False,
                "error": "invalid_profile_state",
                "message": (
                    f"Profile is in {profile.auth_stage}/{profile.kyc_status} state. "
                    "Expected VIDEO_VERIFIED with PROCESSING."
                ),
            }

        if not profile.has_valid_video_task():
            logger.error(f"Profile {profile_id} has no valid video task ID")
            return {"success": False, "error": "missing_video_task_id"}

        video_task_id = profile.video_task_id

    service: IdentityAuthService = get_identity_auth_service()
    try:
        result = service.get_video_verification_result(video_task_id)
    except Exception as e:
        max_retries = getattr(settings, "KYC_VIDEO_CHECK_MAX_RETRIES", 6)
        retry_delay = getattr(settings, "KYC_VIDEO_CHECK_RETRY_DELAY", 120)
        if self.request.retries < max_retries:
            raise self.retry(exc=e, countdown=retry_delay)
        # Mark failed after max retries
        with transaction.atomic():
            try:
                profile = Profile.objects.select_for_update().get(
                    id=profile_id
                )
                profile.update_kyc_result(
                    accepted=False, error_details="failed"
                )
            except Profile.DoesNotExist:
                pass
        logger.error(f"Profile {profile_id}: Network error after max retries")
        return {"success": False, "error": "failed", "message": str(e)}

    # Handle "not ready" signals
    if not result.get("success") and result.get("status") in {404,
                                                              "in_progress",
                                                              "network"}:
        max_retries = getattr(settings, "KYC_VIDEO_CHECK_MAX_RETRIES", 6)
        retry_delay = getattr(settings, "KYC_VIDEO_CHECK_RETRY_DELAY", 120)
        if self.request.retries < max_retries:
            logger.info(
                f"Profile {profile_id}: KYC result not ready; retrying in {retry_delay}s"
            )
            raise self.retry(
                exc=Exception("result_not_ready"), countdown=retry_delay
            )
        with transaction.atomic():
            try:
                profile = Profile.objects.select_for_update().get(
                    id=profile_id
                )
                profile.update_kyc_result(
                    accepted=False, error_details="failed"
                )
            except Profile.DoesNotExist:
                pass
        return {
            "success": False,
            "error": "failed",
            "message": "KYC verification failed after maximum retries",
        }

    # Other service errors
    if not result.get("success"):
        error_msg = result.get("error", "Unknown service error")
        with transaction.atomic():
            try:
                profile = Profile.objects.select_for_update().get(
                    id=profile_id
                )
                profile.update_kyc_result(
                    accepted=False, error_details=str(error_msg)
                )
            except Profile.DoesNotExist:
                pass
        logger.error(f"Profile {profile_id}: Service error - {error_msg}")
        return {
            "success": False, "error": "service_error",
            "message": str(error_msg)
        }

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
            reasons = payload.get("reason", [])
            if isinstance(reasons, list) and reasons:
                reason_msgs = [f"{r.get('code')}: {r.get('message')}" for r in
                               reasons if isinstance(r, dict)]
                logger.info(
                    f"Profile {profile_id}: Rejection reasons: {', '.join(reason_msgs)}"
                )
        else:
            # Fallback criteria
            matching_ok = matching == "TRUE"
            liveness_ok = liveness == "TRUE"
            spoofing_ok = spoofing == "FALSE"
            accepted = matching_ok and liveness_ok and spoofing_ok
    except Exception as e:
        accepted = False
        logger.warning(
            f"Profile {profile_id}: Could not determine result: {e}"
        )

    with transaction.atomic():
        try:
            profile = Profile.objects.select_for_update().get(id=profile_id)
            profile.update_kyc_result(accepted=accepted)
        except Profile.DoesNotExist:
            pass

    if accepted:
        logger.info(f"Profile {profile_id}: KYC verification successful")
    else:
        logger.warning(f"Profile {profile_id}: KYC verification failed")

    # Best-effort: read back final status (may be None if profile went missing)
    final_status = None
    try:
        final_status = Profile.objects.get(id=profile_id).kyc_status
    except Profile.DoesNotExist:
        pass

    return {"success": True, "accepted": accepted, "status": final_status}


@shared_task(bind=True)
def reset_profile_video_kyc(
        self, profile_id: int, reason: str = "manual_reset"
) -> dict:
    """
    Reset a profile's video KYC status back to identity verified stage.
    Useful for retry scenarios or manual intervention.
    """
    try:
        with transaction.atomic():
            profile = Profile.objects.select_for_update().get(id=profile_id)

            # Only allow reset if in-progress or failed/rejected
            if not profile.can_retry_video_kyc() and not profile.is_video_kyc_in_progress():
                logger.warning(
                    f"Profile {profile_id} cannot be reset. "
                    f"Current state: {profile.auth_stage}/{profile.kyc_status}"
                )
                return {
                    "success": False,
                    "error": "invalid_state_for_reset",
                    "message": (
                        f"Profile is in {profile.auth_stage}/{profile.kyc_status} state. "
                        "Cannot reset."
                    ),
                }

            profile.reset_to_identity_verified()

    except Profile.DoesNotExist:
        logger.warning(f"Profile {profile_id} not found for reset operation")
        return {"success": False, "error": "profile_not_found"}
    except ValidationError as e:
        logger.error(
            f"Validation error during reset for profile {profile_id}: {e}"
        )
        return {
            "success": False, "error": "validation_error", "message": str(e)
        }
    except Exception as e:
        logger.error(
            f"Unexpected error during reset for profile {profile_id}: {e}"
        )
        return {"success": False, "error": "reset_failed", "message": str(e)}

    logger.info(
        f"Profile {profile_id}: KYC reset to IDENTITY_VERIFIED stage. Reason: {reason}"
    )
    return {"success": True, "message": "Profile KYC reset successfully"}


@shared_task(bind=True)
def verify_identity_phone_national_id(self, profile_id: int) -> dict:
    """
    Verify phone number and national ID matching using Shahkar API.
    Updates phone_national_id_match_status and auth_stage based on verification result.
    """
    try:
        profile = Profile.objects.get(id=profile_id)
    except Profile.DoesNotExist:
        return {"success": False, "error": "profile_not_found"}

    # Required inputs
    if not profile.national_id or not profile.phone_number:
        logger.warning(
            f"Profile {profile_id}: Missing national_id or phone_number"
        )
        return {
            "success": False,
            "error": "missing_required_fields",
            "message": "National ID and phone number are required",
        }

    service: IdentityAuthService = get_identity_auth_service()
    try:
        result = service.verify_mobile_national_id(
            national_code=profile.national_id,
            mobile_number=profile.phone_number,
        )
    except Exception as e:
        max_retries = getattr(settings, "KYC_SHAHKAR_MAX_RETRIES", 3)
        retry_delay = getattr(settings, "KYC_SHAHKAR_RETRY_DELAY", 60)
        if self.request.retries < max_retries:
            logger.warning(
                f"Profile {profile_id}: Shahkar API error, retrying: {e}"
            )
            raise self.retry(exc=e, countdown=retry_delay)
        logger.error(
            f"Profile {profile_id}: Shahkar API error after max retries: {e}"
        )
        return {
            "success": False, "error": "service_unavailable", "message": str(e)
        }

    if not result.get("success"):
        error_msg = result.get("error", "Unknown service error")
        is_validation_error = result.get("is_validation_error", False)

        if is_validation_error:
            # Validation error → mark FAILED
            with transaction.atomic():
                try:
                    p = Profile.objects.select_for_update().get(id=profile_id)
                    p.phone_national_id_match_status = KYCStatus.FAILED
                    p.save(
                        update_fields=["phone_national_id_match_status",
                                       "updated_at"]
                    )
                except Profile.DoesNotExist:
                    pass

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
            return {"success": False, "error": "profile_not_found"}

        if is_matched:
            p.mark_identity_verified()
            logger.info(
                f"Profile {profile_id}: Phone/National ID verification successful"
            )
            return {
                "success": True,
                "is_matched": True,
                "message": "Identity verification completed successfully",
            }

        p.phone_national_id_match_status = KYCStatus.REJECTED
        p.save(update_fields=["phone_national_id_match_status", "updated_at"])
        logger.warning(
            f"Profile {profile_id}: Phone/National ID verification failed - not matched"
        )
        return {
            "success": True,
            "is_matched": False,
            "message": "Phone number and national ID do not match",
        }
