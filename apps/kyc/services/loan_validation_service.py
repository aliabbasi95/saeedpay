# apps/kyc/services/loan_validation_service.py

import logging
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


class LoanValidationService:
    """
    Service for loan validation and credit scoring through external KYC provider.

    This service acts as an intermediary between the application and the external
    loan validation API. It handles:
    1. Sending OTP to user for loan validation
    2. Verifying OTP and requesting credit report
    3. Retrieving the credit report with score

    Token management is handled by the parent IdentityAuthService.
    """

    def __init__(self, base_url: str, timeout: int = 30):
        """
        Initialize the loan validation service.

        Args:
            base_url: Base URL of the KYC identity service
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.timeout = timeout

    def send_otp(
        self, national_code: str, mobile_number: str, access_token: str
    ) -> dict:
        """
        Send OTP to user's mobile for loan validation.

        Args:
            national_code: User's national ID
            mobile_number: User's mobile number (e.g., "09123456789")
            access_token: Valid access token for authentication

        Returns:
            Dict containing:
                - success: bool
                - unique_id: str (if successful)
                - message: str
                - error: str (if failed)
                - error_code: str (if failed)
        """
        if not all([national_code, mobile_number, access_token]):
            return {
                "success": False,
                "error": "Missing required parameters",
                "error_code": "MISSING_PARAMS",
            }

        url = urljoin(self.base_url.rstrip("/") + "/", "api/inq/loan-validation/otp")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": "SaeedPay-KYC-Service/1.0",
        }
        payload = {
            "nationalCode": national_code,
            "mobileNumber": mobile_number,
        }

        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=self.timeout
            )

            if response.status_code == 200:
                try:
                    resp_json = response.json()
                    data = resp_json.get("data", {})
                    details = data.get("details", {})
                    unique_id = resp_json.get("uniqueId")

                    if details.get("success"):
                        logger.info(
                            f"OTP sent successfully for national_code: {national_code}"
                        )
                        return {
                            "success": True,
                            "unique_id": unique_id,
                            "message": data.get("message", "OTP sent successfully"),
                            "raw": resp_json,
                        }
                    else:
                        logger.warning(
                            f"OTP sending failed for national_code: {national_code}"
                        )
                        return {
                            "success": False,
                            "error": data.get("message", "Failed to send OTP"),
                            "error_code": "OTP_SEND_FAILED",
                            "raw": resp_json,
                        }
                except Exception as e:
                    logger.error(f"Invalid JSON in OTP response: {e}")
                    return {
                        "success": False,
                        "error": "Invalid response format",
                        "error_code": "INVALID_JSON",
                    }
            elif response.status_code == 400:
                # Handle validation errors
                try:
                    resp_json = response.json()
                    error_obj = resp_json.get("error", {})
                    error_message = error_obj.get("message", "Validation error")
                    error_code = error_obj.get("code")

                    logger.warning(
                        f"OTP validation error: {error_message} (code: {error_code})"
                    )
                    return {
                        "success": False,
                        "error": error_message,
                        "error_code": (
                            f"VALIDATION_ERROR_{error_code}"
                            if error_code
                            else "VALIDATION_ERROR"
                        ),
                        "status": 400,
                        "is_validation_error": True,
                        "raw": resp_json,
                    }
                except Exception as e:
                    logger.error(f"Failed to parse 400 error response: {e}")
                    return {
                        "success": False,
                        "error": (
                            response.text[:500]
                            if response.text
                            else "Validation failed"
                        ),
                        "error_code": "VALIDATION_ERROR",
                        "status": 400,
                        "is_validation_error": True,
                    }
            else:
                error_body = response.text[:500] if response.text else ""
                logger.error(
                    f"OTP send failed: HTTP {response.status_code} | {error_body}"
                )
                return {
                    "success": False,
                    "error": error_body or "Failed to send OTP",
                    "error_code": "SERVICE_ERROR",
                    "status": response.status_code,
                }

        except requests.exceptions.Timeout:
            logger.error(f"OTP send timeout for national_code: {national_code}")
            return {
                "success": False,
                "error": "Request timeout",
                "error_code": "TIMEOUT",
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"OTP send request failed: {e}")
            return {
                "success": False,
                "error": f"Network error: {str(e)}",
                "error_code": "NETWORK_ERROR",
            }
        except Exception as e:
            logger.error(f"Unexpected error during OTP send: {e}")
            return {
                "success": False,
                "error": "Unexpected error",
                "error_code": "UNEXPECTED_ERROR",
            }

    @staticmethod
    def _coerce_score(value):
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _normalize_report_response(self, resp_json: dict) -> dict:
        """Normalize provider responses to SaeedPay's stable backend contract."""
        data = resp_json.get("data") or {}
        error_obj = resp_json.get("error")

        if error_obj:
            error_message = error_obj.get("message", "Loan validation failed")
            error_code = error_obj.get("code")
            return {
                "success": False,
                "completed": False,
                "error": error_message,
                "error_code": error_code or "LOAN_VALIDATION_FAILED",
                "raw": resp_json,
            }

        message = data.get("message", "Report request accepted")
        unique_id = resp_json.get("uniqueId")
        details = data.get("details")

        # The new provider flow returns details=null while the report is being built.
        if details is None:
            return {
                "success": True,
                "completed": False,
                "processing": True,
                "status": "IN_PROCESSING",
                "unique_id": unique_id,
                "message": message,
                "timestamp": resp_json.get("timestamp"),
                "raw": resp_json,
            }

        if not isinstance(details, dict):
            return {
                "success": False,
                "completed": False,
                "error": "Invalid report details format",
                "error_code": "INVALID_REPORT_DETAILS",
                "raw": resp_json,
            }

        json_data = details.get("jsonData")
        if isinstance(json_data, str):
            try:
                import json

                json_data = json.loads(json_data)
            except (TypeError, ValueError):
                return {
                    "success": False,
                    "completed": False,
                    "error": "Invalid JSON report payload",
                    "error_code": "INVALID_REPORT_JSON",
                    "raw": resp_json,
                }

        # Backward compatibility with the legacy report-json schema.
        if isinstance(json_data, dict) and isinstance(json_data.get("score"), dict):
            score_data = json_data.get("score") or {}
            person_info = score_data.get("personInformation") or {}
            return {
                "success": True,
                "completed": True,
                "processing": False,
                "status": "DONE",
                "report_data": json_data,
                "score": self._coerce_score(score_data.get("score")),
                "risk": score_data.get("risk"),
                "grade_description": person_info.get("gradeDescription"),
                "person_info": person_info,
                "score_codes": score_data.get("scoreCodes", []),
                "report_types": json_data.get("reportTypes"),
                "message": message,
                "unique_id": unique_id,
                "timestamp": resp_json.get("timestamp"),
                "raw": resp_json,
            }

        if not isinstance(json_data, dict):
            # The application needs structured data to derive score/risk. A PDF-only
            # response is valid for the provider but not sufficient for our backend.
            if details.get("contentBase64"):
                return {
                    "success": False,
                    "completed": False,
                    "error": "Provider returned a PDF-only report; JSON output is required",
                    "error_code": "UNSUPPORTED_REPORT_OUTPUT",
                    "raw": resp_json,
                }
            return {
                "success": True,
                "completed": False,
                "processing": True,
                "status": "IN_PROCESSING",
                "unique_id": unique_id,
                "message": message,
                "timestamp": resp_json.get("timestamp"),
                "raw": resp_json,
            }

        provider_status = str(json_data.get("status") or "").upper()
        report_data = json_data.get("data")

        if provider_status != "DONE":
            return {
                "success": True,
                "completed": False,
                "processing": True,
                "status": provider_status or "IN_PROCESSING",
                "assessment_id": json_data.get("assessmentId"),
                "report_level": json_data.get("level"),
                "output_type": json_data.get("outputType"),
                "unique_id": unique_id,
                "message": message,
                "timestamp": resp_json.get("timestamp"),
                "raw": resp_json,
            }

        if not isinstance(report_data, dict):
            return {
                "success": False,
                "completed": False,
                "error": "Completed report has no structured data",
                "error_code": "INVALID_COMPLETED_REPORT",
                "raw": resp_json,
            }

        credit_score_data = report_data.get("creditScore") or {}
        if not isinstance(credit_score_data, dict):
            credit_score_data = {}

        report_information = report_data.get("reportInformation") or {}
        if not isinstance(report_information, dict):
            report_information = {}

        report_level = (
            report_information.get("reportLevel")
            or json_data.get("level")
        )
        report_types = report_data.get("reportTypes")
        if not report_types and report_level:
            report_types = [report_level]

        return {
            "success": True,
            "completed": True,
            "processing": False,
            "status": provider_status,
            "assessment_id": json_data.get("assessmentId"),
            "report_level": report_level,
            "output_type": json_data.get("outputType"),
            "report_data": report_data,
            "score": self._coerce_score(credit_score_data.get("score")),
            "risk": credit_score_data.get("risk"),
            "grade_description": credit_score_data.get("riskDescription"),
            "score_factors": credit_score_data.get("scoreFactorList", []),
            "score_reasons": credit_score_data.get("scoreReasonList", []),
            "report_types": report_types,
            "message": message,
            "unique_id": unique_id,
            "timestamp": resp_json.get("timestamp"),
            "raw": resp_json,
        }

    def _request_report(
        self, otp_code: str, unique_id: str, access_token: str
    ) -> dict:
        if not all([otp_code, unique_id, access_token]):
            return {
                "success": False,
                "completed": False,
                "error": "Missing required parameters",
                "error_code": "MISSING_PARAMS",
            }

        url = urljoin(
            self.base_url.rstrip("/") + "/", "api/inq/loan-validation/request-report"
        )
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": "SaeedPay-KYC-Service/1.0",
        }
        payload = {
            "otpCode": otp_code,
            "uniqueId": unique_id,
        }

        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=self.timeout
            )

            try:
                resp_json = response.json()
            except Exception as exc:
                logger.error("Invalid JSON in loan report response: %s", exc)
                return {
                    "success": False,
                    "completed": False,
                    "error": "Invalid response format",
                    "error_code": "INVALID_JSON",
                }

            if response.status_code == 200:
                result = self._normalize_report_response(resp_json)
                if result.get("completed"):
                    logger.info(
                        "Loan report completed: unique_id=%s score=%s risk=%s",
                        unique_id,
                        result.get("score"),
                        result.get("risk"),
                    )
                elif result.get("success"):
                    logger.info(
                        "Loan report still processing: unique_id=%s status=%s",
                        unique_id,
                        result.get("status"),
                    )
                return result

            if response.status_code == 400:
                error_obj = resp_json.get("error") or {}
                error_message = error_obj.get("message", "Validation error")
                error_code = error_obj.get("code")
                logger.warning(
                    "Loan report validation error: %s (code: %s)",
                    error_message,
                    error_code,
                )
                return {
                    "success": False,
                    "completed": False,
                    "error": error_message,
                    "error_code": error_code or "VALIDATION_ERROR",
                    "status": 400,
                    "is_validation_error": True,
                    "is_otp_error": True,
                    "retryable": False,
                    "raw": resp_json,
                }

            error_body = response.text[:500] if response.text else ""
            logger.error(
                "Loan report request failed: HTTP %s | %s",
                response.status_code,
                error_body,
            )
            return {
                "success": False,
                "completed": False,
                "error": error_body or "Failed to request report",
                "error_code": "SERVICE_ERROR",
                "status": response.status_code,
                "retryable": response.status_code >= 500,
            }

        except requests.exceptions.Timeout:
            logger.error("Loan report request timeout")
            return {
                "success": False,
                "completed": False,
                "error": "Request timeout",
                "error_code": "TIMEOUT",
                "retryable": True,
            }
        except requests.exceptions.RequestException as exc:
            logger.error("Loan report request failed: %s", exc)
            return {
                "success": False,
                "completed": False,
                "error": f"Network error: {str(exc)}",
                "error_code": "NETWORK_ERROR",
                "retryable": True,
            }
        except Exception as exc:
            logger.exception("Unexpected error during loan report request")
            return {
                "success": False,
                "completed": False,
                "error": str(exc) or "Unexpected error",
                "error_code": "UNEXPECTED_ERROR",
                "retryable": False,
            }

    def verify_otp_and_request_report(
        self, otp_code: str, unique_id: str, access_token: str
    ) -> dict:
        """Verify OTP and start (or return) the new structured credit report."""
        return self._request_report(otp_code, unique_id, access_token)

    def get_report_result(
        self, unique_id: str, otp_code: str, access_token: str
    ) -> dict:
        """
        Poll the new loan validation flow.

        The provider no longer exposes the legacy ``report-json`` endpoint for
        this flow. Repeating ``request-report`` with the original OTP and
        unique ID returns either a processing response or the completed JSON
        report.
        """
        return self._request_report(otp_code, unique_id, access_token)
