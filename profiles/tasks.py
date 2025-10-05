from celery import shared_task
from django.db import transaction
from django.core.exceptions import ValidationError
import logging
import os

from profiles.models import Profile
from profiles.utils.choices import KYCStatus, AuthenticationStage
from kyc.services.identity_auth_service import (
    IdentityAuthService,
    get_identity_auth_service,
)
from django.conf import settings

logger = logging.getLogger(__name__)


def _cleanup_temp_file(file_path: str) -> None:
    """Helper to safely clean up temporary files."""
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
    Submit video KYC for the given profile and persist tracking fields.
    Sets profile.auth_stage to VIDEO_VERIFIED and kyc_status to PROCESSING.
    """
    # First, validate profile state in a transaction
    with transaction.atomic():
        try:
            profile = Profile.objects.select_for_update().get(id=profile_id)
        except Profile.DoesNotExist:
            return {"success": False, "error": "profile_not_found"}

        # Validate that profile is in correct state for video KYC
        if not profile.can_submit_video_kyc():
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

        # Check if video KYC is already in progress (prevents duplicate submissions)
        if profile.is_video_kyc_in_progress():
            logger.warning(
                f"Profile {profile_id} already has video KYC in progress. "
                f"Current status: {profile.kyc_status}"
            )
            return {
                "success": False,
                "error": "kyc_in_progress",
                "message": "Video KYC is already in progress for this profile.",
            }

        # Check if already accepted
        if profile.kyc_status == KYCStatus.ACCEPTED:
            logger.warning(
                f"Profile {profile_id} already has accepted KYC status."
            )
            return {
                "success": False,
                "error": "already_accepted",
                "message": "Profile already has accepted KYC status.",
            }
    # Transaction ends here - lock is released

    # Call KYC service OUTSIDE transaction to avoid holding lock during API call
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
        # Clean up temporary file on error
        _cleanup_temp_file(selfie_video_path)
        # Network or unexpected error → retry
        max_retries = getattr(settings, "KYC_VIDEO_SUBMIT_MAX_RETRIES", 3)
        retry_delay = getattr(settings, "KYC_VIDEO_SUBMIT_RETRY_DELAY", 60)
        if self.request.retries < max_retries:
            raise self.retry(exc=e, countdown=retry_delay)
        return {"success": False, "error": "service_unavailable", "message": str(e)}

    # Check if service call was successful
    if not result.get("success"):
        _cleanup_temp_file(selfie_video_path)
        error_msg = result.get("error", "Unknown service error")
        return {"success": False, "error": "service_error", "message": error_msg}

    # Extract uniqueId from the response
    # Response format: {"success": True, "data": {"uniqueId": "...", "data": {...}}}
    data = (result or {}).get("data") or {}
    unique_id = data.get("uniqueId")

    if not unique_id:
        logger.error(f"Profile {profile_id}: No unique ID returned from KYC service")
        _cleanup_temp_file(selfie_video_path)
        return {
            "success": False,
            "error": "missing_unique_id",
            "message": "No unique ID returned from KYC service",
        }

    # Clean up temporary file after successful submission
    _cleanup_temp_file(selfie_video_path)

    # Update profile with the unique_id in a new transaction
    with transaction.atomic():
        try:
            # Refresh profile to get latest state
            profile = Profile.objects.select_for_update().get(id=profile_id)
            profile.mark_video_submitted(task_id=unique_id)
            logger.info(
                f"Profile {profile_id}: Successfully submitted video KYC. "
                f"Task ID: {unique_id}, new status: {profile.kyc_status}"
            )
        except ValidationError as e:
            logger.error(
                f"Profile {profile_id}: Validation error during video KYC submission: {e}"
            )
            return {"success": False, "error": "validation_error", "message": str(e)}

        # Schedule result check after transaction commits
        # Use transaction.on_commit to ensure profile changes are visible
        transaction.on_commit(
            lambda: check_profile_video_kyc_result.apply_async((profile_id,), countdown=30)
        )
        logger.info(f"Profile {profile_id}: Scheduled result check task in 30 seconds")

    return {"success": True, "unique_id": unique_id}


@shared_task(bind=True)
def check_profile_video_kyc_result(self, profile_id: int) -> dict:
    """
    Poll the provider for video KYC result; update profile. Reschedules itself
    if the result is not yet ready.
    """
    # Wrap in transaction to make select_for_update effective
    with transaction.atomic():
        try:
            profile = Profile.objects.select_for_update().get(id=profile_id)
        except Profile.DoesNotExist:
            return {"success": False, "error": "profile_not_found"}

        # Validate that profile is in correct state for checking results
        if not profile.is_video_kyc_in_progress():
            logger.warning(
                f"Profile {profile_id} is not in correct state for KYC result check. "
                f"Current: {profile.auth_stage}/{profile.kyc_status}"
            )
            return {
                "success": False,
                "error": "invalid_profile_state",
                "message": (
                    f"Profile is in {profile.auth_stage}/{profile.kyc_status} state. "
                    "Expected VIDEO_VERIFIED with PROCESSING KYC status."
                ),
            }

        if not profile.has_valid_video_task():
            logger.error(f"Profile {profile_id} has no valid video task ID")
            return {"success": False, "error": "missing_video_task_id"}
        
        # Store video_task_id before releasing lock
        video_task_id = profile.video_task_id
    # Transaction ends here - lock is released

    # Call service OUTSIDE transaction to avoid holding lock during API call
    service: IdentityAuthService = get_identity_auth_service()
    try:
        result = service.get_video_verification_result(video_task_id)
    except Exception as e:

        max_retries = getattr(settings, "KYC_VIDEO_CHECK_MAX_RETRIES", 6)
        retry_delay = getattr(settings, "KYC_VIDEO_CHECK_RETRY_DELAY", 120)
        if self.request.retries < max_retries:
            raise self.retry(exc=e, countdown=retry_delay)
        # Mark as network error after max retries
        with transaction.atomic():
            profile.update_kyc_result(accepted=False, error_details="failed")
        logger.error(f"Profile {profile_id}: Network error after max retries")
        return {"success": False, "error": "failed", "message": str(e)}

    # If provider still not ready, schedule another check
    if not result.get("success") and result.get("status") in {404, "in_progress", "network"}:

        max_retries = getattr(settings, "KYC_VIDEO_CHECK_MAX_RETRIES", 6)
        retry_delay = getattr(settings, "KYC_VIDEO_CHECK_RETRY_DELAY", 120)
        if self.request.retries < max_retries:
            logger.info(
                f"Profile {profile_id}: KYC result not ready, retrying in {retry_delay}s"
            )
            raise self.retry(exc=Exception("result_not_ready"), countdown=retry_delay)
        # Give up after max retries but mark as failed instead of keeping processing
        with transaction.atomic():
            profile.update_kyc_result(accepted=False, error_details="failed")
        logger.warning(
            f"Profile {profile_id}: KYC verification failed after maximum retries"
        )
        return {
            "success": False,
            "error": "failed",
            "message": "KYC verification failed after maximum retries",
        }

    # Check for other service errors
    if not result.get("success"):
        error_msg = result.get("error", "Unknown service error")
        with transaction.atomic():
            profile.update_kyc_result(accepted=False, error_details=str(error_msg))
        logger.error(f"Profile {profile_id}: Service error - {error_msg}")
        return {"success": False, "error": "service_error", "message": str(error_msg)}

    accepted = False
    try:
        verify_status = result.get("verifyStatus", "").upper()
        matching = result.get("matching", "").upper()
        liveness = result.get("liveness", "").upper()
        spoofing = result.get("spoofing", "").upper()
        
        # Check if verification was explicitly accepted
        if verify_status == "ACCEPT":
            accepted = True
        elif verify_status == "REJECT":
            accepted = False
            # Log rejection reasons if available
            reasons = result.get("reason", [])
            if reasons:
                reason_msgs = [f"{r.get('code')}: {r.get('message')}" for r in reasons]
                logger.info(f"Profile {profile_id}: Rejection reasons: {', '.join(reason_msgs)}")
        else:
            # Fallback to checking individual criteria
            matching_bool = matching == "TRUE"
            liveness_bool = liveness == "TRUE"
            spoofing_bool = spoofing == "FALSE"
            
            # Accept if all criteria are met
            if matching_bool and liveness_bool and spoofing_bool:
                accepted = True
    except Exception as e:
        # If we can't determine the result, mark as failed
        accepted = False
        logger.warning(
            f"Profile {profile_id}: Could not determine KYC result from API response: {e}"
        )

    with transaction.atomic():
        profile.update_kyc_result(accepted=accepted)

    if accepted:
        logger.info(f"Profile {profile_id}: KYC verification successful")
    else:
        logger.warning(f"Profile {profile_id}: KYC verification failed")

    return {"success": True, "accepted": accepted, "status": profile.kyc_status}


@shared_task(bind=True)
def reset_profile_video_kyc(self, profile_id: int, reason: str = "manual_reset") -> dict:
    """
    Reset a profile's video KYC status back to identity verified stage.
    Useful for retry scenarios or manual intervention.
    """
    try:
        profile = Profile.objects.select_for_update().get(id=profile_id)
    except Profile.DoesNotExist:
        logger.warning(f"Profile {profile_id} not found for reset operation")
        return {"success": False, "error": "profile_not_found"}
    except Exception as e:
        logger.error(f"Unexpected error retrieving profile {profile_id}: {e}")
        return {"success": False, "error": "unexpected_error", "message": str(e)}

    # Check if reset is allowed
    try:
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
    except Exception as e:
        logger.error(f"Error checking reset conditions for profile {profile_id}: {e}")
        return {"success": False, "error": "validation_error", "message": str(e)}

    try:
        with transaction.atomic():
            profile.reset_to_identity_verified()
    except ValidationError as e:
        logger.error(f"Validation error during reset for profile {profile_id}: {e}")
        return {"success": False, "error": "validation_error", "message": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error during reset for profile {profile_id}: {e}")
        return {"success": False, "error": "reset_failed", "message": str(e)}

    logger.info(
        f"Profile {profile_id}: KYC reset to IDENTITY_VERIFIED stage. "
        f"Reason: {reason}"
    )

    return {"success": True, "message": "Profile KYC reset successfully"}


@shared_task(bind=True)
def verify_identity_phone_national_id(self, profile_id: int) -> dict:
    """
    Verify phone number and national ID matching using Shahkar API.
    Updates phone_national_id_match_status and auth_stage based on verification result.
    """
    # First, fetch profile data
    try:
        profile = Profile.objects.get(id=profile_id)
    except Profile.DoesNotExist:
        return {"success": False, "error": "profile_not_found"}

    # Validate required fields
    if not profile.national_id or not profile.phone_number:
        logger.warning(f"Profile {profile_id}: Missing national_id or phone_number")
        return {
            "success": False,
            "error": "missing_required_fields",
            "message": "National ID and phone number are required",
        }

    # Call Shahkar verification service
    service: IdentityAuthService = get_identity_auth_service()
    try:
        result = service.verify_mobile_national_id(
            national_code=profile.national_id,
            mobile_number=profile.phone_number,
        )
    except Exception as e:
        # Network or unexpected error → retry
        max_retries = getattr(settings, "KYC_SHAHKAR_MAX_RETRIES", 3)
        retry_delay = getattr(settings, "KYC_SHAHKAR_RETRY_DELAY", 60)
        if self.request.retries < max_retries:
            logger.warning(f"Profile {profile_id}: Shahkar API error, retrying: {e}")
            raise self.retry(exc=e, countdown=retry_delay)
        logger.error(f"Profile {profile_id}: Shahkar API error after max retries: {e}")
        return {"success": False, "error": "service_unavailable", "message": str(e)}

    # Check if service call was successful
    if not result.get("success"):
        error_msg = result.get("error", "Unknown service error")
        logger.error(f"Profile {profile_id}: Shahkar verification service error - {error_msg}")
        return {"success": False, "error": "service_error", "message": error_msg}

    # Update profile based on verification result
    is_matched = result.get("is_matched", False)
    
    with transaction.atomic():
        # Refresh profile to get latest state
        profile = Profile.objects.select_for_update().get(id=profile_id)
        
        if is_matched:
            profile.phone_national_id_match_status = KYCStatus.ACCEPTED
            profile.mark_identity_verified()
            logger.info(
                f"Profile {profile_id}: Phone/National ID verification successful"
            )
            return {
                "success": True,
                "is_matched": True,
                "message": "Identity verification completed successfully",
            }
        else:
            profile.phone_national_id_match_status = KYCStatus.REJECTED
            profile.save(update_fields=["phone_national_id_match_status", "updated_at"])
            logger.warning(
                f"Profile {profile_id}: Phone/National ID verification failed - not matched"
            )
            return {
                "success": True,
                "is_matched": False,
                "message": "Phone number and national ID do not match",
            }
