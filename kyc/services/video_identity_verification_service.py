import logging
import os
import time
import requests
from typing import Optional, Dict, Any, Callable
from django.conf import settings
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class VideoIdentityVerificationService:
    """
    Service for handling video-based identity verification via external API.
    This service requires an access token to be passed for each request.
    """

    def __init__(self):
        self.base_url = getattr(settings, "KYC_IDENTITY_BASE_URL", "")
        self.timeout = getattr(settings, "KYC_IDENTITY_TIMEOUT", 30)
        self.session = requests.Session()
        if not self.base_url:
            logger.warning("Video Identity Verification service: base_url not configured")


    def verify_idcard_video(
        self,
        national_code: str,
        birth_date: str,
        selfie_video_path: str,
        rand_action: str,
        access_token: str,
        matching_thr: Optional[int] = None,
        liveness_thr: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Send video-based identity verification request.
        Args:
            national_code: National ID number
            birth_date: Date of birth (YYYYMMDD format)
            selfie_video_path: Path to selfie video file
            rand_action: Random action string
            access_token: Bearer token for authentication
            matching_thr: (optional) facial matching threshold
            liveness_thr: (optional) liveness threshold
        Returns:
            Dict with API response or error info
        """
        # Validate inputs
        if not access_token:
            logger.error("Access token is required for video verification")
            return {"success": False, "error": "access_token_required", "status": "validation_error"}
        
        if not selfie_video_path or not selfie_video_path.strip():
            logger.error("Selfie video file path is empty or None")
            return {"success": False, "error": "selfie_video_file_path_empty", "status": "validation_error"}

        if not os.path.exists(selfie_video_path):
            logger.error(f"Selfie video file not found: {selfie_video_path}")
            return {"success": False, "error": "selfie_video_file_not_found", "status": "file_error"}
        
        # Prepare request
        url = urljoin(self.base_url.rstrip("/") + "/", "api/vvs/video/verify-idcard-img")
        headers = {"Authorization": f"Bearer {access_token}", "User-Agent": "SaeedPay-KYC-Service/1.0"}
        data = {"nationalCode": national_code, "birthDate": birth_date, "randAction": rand_action}
        
        if matching_thr is not None:
            data["matchingTHR"] = str(matching_thr)
        if liveness_thr is not None:
            data["livenessTHR"] = str(liveness_thr)

        try:
            with open(selfie_video_path, "rb") as video_file:

                files = {
                    "selfieVideo": (
                        os.path.basename(selfie_video_path),
                        video_file,
                        "video/mp4",
                    )
                }
                response = self.session.post(
                    url, data=data, files=files, headers=headers, timeout=self.timeout
                )
            if response.status_code == 200:
                try:
                    return {"success": True, "data": response.json()}
                except Exception:
                    logger.error("Invalid JSON in success response")
                    return {"success": False, "error": "Invalid JSON in success response"}
            elif response.status_code == 400:
                try:
                    return {"success": False, "error": response.json().get("error", {}), "status": 400}
                except Exception:
                    logger.error("Invalid JSON in error response (400)")
                    return {"success": False, "error": "Invalid JSON in error response (400)", "status": 400}
            else:
                logger.error(f"Unexpected status {response.status_code}: {response.text}")
                return {"success": False, "error": response.text, "status": response.status_code}
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error: {e}")
            return {"success": False, "error": str(e), "status": "network"}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"success": False, "error": str(e), "status": "exception"}

    def get_verification_result(self, unique_id: str, access_token: str) -> Dict[str, Any]:
        """
        Fetch the result of a video-based identity verification by uniqueId.
        Args:
            unique_id: Unique identifier from the verification submission
            access_token: Bearer token for authentication
        Returns:
            Dict with success status, result details if available, or error info
        """
        if not access_token:
            logger.error("Access token is required for fetching verification result")
            return {
                "success": False,
                "error": "access_token_required",
                "status": "validation_error",
            }
        
        url = urljoin(self.base_url.rstrip("/") + "/", "api/vvs/video/verify/result")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "SaeedPay-KYC-Service/1.0",
        }
        params = {"uniqueId": unique_id}
        try:
            response = self.session.get(
                url, headers=headers, params=params, timeout=self.timeout
            )
            if response.status_code == 200:
                try:
                    resp_json = response.json()
                    data = resp_json.get("data", {})
                    details = data.get("details", {})
                    
                    # Extract verification status
                    verify_status = details.get("verifyStatus")
                    
                    # If still in progress, return not ready
                    if verify_status == "IN_PROGRESS":
                        return {
                            "success": False,
                            "status": "in_progress",
                            "error": "Verification still in progress",
                            "raw": resp_json,
                        }
                    
                    # Extract verification details
                    return {
                        "success": True,
                        "matching": details.get("matching"),
                        "liveness": details.get("liveness"),
                        "spoofing": details.get("spoofing"),
                        "spoofingDoubleCheck": details.get("spoofingDoubleCheck"),
                        "verifyStatus": verify_status,
                        "verifyStatusMsg": details.get("verifyStatusMsg"),
                        "reason": details.get("reason", []),
                        "raw": resp_json,
                    }
                except Exception as e:
                    logger.error(f"Invalid JSON in success response: {e}")
                    return {
                        "success": False,
                        "error": "Invalid JSON in success response",
                        "status": "parse_error",
                    }
            elif response.status_code == 404:
                # Result not yet available
                logger.info(f"Verification result not yet available for {unique_id}")
                return {
                    "success": False,
                    "error": "Result not yet available",
                    "status": 404,
                }
            else:
                try:
                    err_json = response.json()
                    logger.error(f"Unexpected status {response.status_code}: {err_json}")
                    return {
                        "success": False,
                        "error": err_json,
                        "status": response.status_code,
                    }
                except Exception:
                    logger.error(
                        f"Unexpected status {response.status_code}: {response.text}"
                    )
                    return {
                        "success": False,
                        "error": response.text,
                        "status": response.status_code,
                    }
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error: {e}")
            return {"success": False, "error": str(e), "status": "network"}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {
                "success": False,
                "error": str(e),
                "status": "exception",
            }
