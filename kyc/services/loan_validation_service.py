# kyc/services/loan_validation_service.py

import logging
import requests
from typing import Dict, Optional
from urllib.parse import urljoin

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

    def send_otp(self, national_code: str, mobile_number: str, access_token: str) -> Dict:
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
                    
                    logger.warning(f"OTP validation error: {error_message} (code: {error_code})")
                    return {
                        "success": False,
                        "error": error_message,
                        "error_code": f"VALIDATION_ERROR_{error_code}" if error_code else "VALIDATION_ERROR",
                        "status": 400,
                        "is_validation_error": True,
                        "raw": resp_json,
                    }
                except Exception as e:
                    logger.error(f"Failed to parse 400 error response: {e}")
                    return {
                        "success": False,
                        "error": response.text[:500] if response.text else "Validation failed",
                        "error_code": "VALIDATION_ERROR",
                        "status": 400,
                        "is_validation_error": True,
                    }
            else:
                error_body = response.text[:500] if response.text else ""
                logger.error(f"OTP send failed: HTTP {response.status_code} | {error_body}")
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

    def verify_otp_and_request_report(
        self, otp_code: str, unique_id: str, access_token: str
    ) -> Dict:
        """
        Verify OTP and request credit report generation.
        
        Args:
            otp_code: OTP code received by user
            unique_id: Unique ID from send_otp step
            access_token: Valid access token for authentication
            
        Returns:
            Dict containing:
                - success: bool
                - status: str ("InProcessing" if successful)
                - unique_id: str (new unique_id for tracking report)
                - message: str
                - error: str (if failed)
                - error_code: str/int (if failed)
        """
        if not all([otp_code, unique_id, access_token]):
            return {
                "success": False,
                "error": "Missing required parameters",
                "error_code": "MISSING_PARAMS",
            }

        url = urljoin(self.base_url.rstrip("/") + "/", "api/inq/loan-validation/request-report")
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
            except Exception as e:
                logger.error(f"Invalid JSON in verify OTP response: {e}")
                return {
                    "success": False,
                    "error": "Invalid response format",
                    "error_code": "INVALID_JSON",
                }

            if response.status_code == 200:
                data = resp_json.get("data", {})
                error_obj = resp_json.get("error")
                
                if error_obj:
                    # Error in response body
                    error_message = error_obj.get("message", "OTP verification failed")
                    error_code = error_obj.get("code")
                    
                    logger.warning(f"OTP verification error: {error_message} (code: {error_code})")
                    return {
                        "success": False,
                        "error": error_message,
                        "error_code": error_code or "OTP_VERIFICATION_FAILED",
                        "is_otp_error": True,
                        "raw": resp_json,
                    }
                
                # Success case
                details = data.get("details", {})
                report_status = details.get("status")
                new_unique_id = resp_json.get("uniqueId")
                
                logger.info(f"Report requested successfully: {new_unique_id}, status: {report_status}")
                return {
                    "success": True,
                    "status": report_status,
                    "unique_id": new_unique_id,
                    "message": data.get("message", "Report requested successfully"),
                    "raw": resp_json,
                }
            
            elif response.status_code == 400:
                # Handle validation errors
                error_obj = resp_json.get("error", {})
                error_message = error_obj.get("message", "Validation error")
                error_code = error_obj.get("code")
                
                logger.warning(f"Report request validation error: {error_message} (code: {error_code})")
                return {
                    "success": False,
                    "error": error_message,
                    "error_code": error_code or "VALIDATION_ERROR",
                    "status": 400,
                    "is_validation_error": True,
                    "raw": resp_json,
                }
            else:
                error_body = response.text[:500] if response.text else ""
                logger.error(f"Report request failed: HTTP {response.status_code} | {error_body}")
                return {
                    "success": False,
                    "error": error_body or "Failed to request report",
                    "error_code": "SERVICE_ERROR",
                    "status": response.status_code,
                }

        except requests.exceptions.Timeout:
            logger.error("Report request timeout")
            return {
                "success": False,
                "error": "Request timeout",
                "error_code": "TIMEOUT",
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Report request failed: {e}")
            return {
                "success": False,
                "error": f"Network error: {str(e)}",
                "error_code": "NETWORK_ERROR",
            }
        except Exception as e:
            logger.error(f"Unexpected error during report request: {e}")
            return {
                "success": False,
                "error": "Unexpected error",
                "error_code": "UNEXPECTED_ERROR",
            }

    def get_report_result(self, unique_id: str, access_token: str) -> Dict:
        """
        Retrieve the credit report result.
        
        Args:
            unique_id: Unique ID from verify_otp_and_request_report step
            access_token: Valid access token for authentication
            
        Returns:
            Dict containing:
                - success: bool
                - report_data: dict (full JSON report if successful)
                - score: int (credit score if successful)
                - risk: str (risk level if successful)
                - grade_description: str (risk description if successful)
                - message: str
                - error: str (if failed)
                - error_code: str (if failed)
        """
        if not all([unique_id, access_token]):
            return {
                "success": False,
                "error": "Missing required parameters",
                "error_code": "MISSING_PARAMS",
            }

        url = urljoin(self.base_url.rstrip("/") + "/", "api/inq/loan-validation/request-report")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": "SaeedPay-KYC-Service/1.0",
        }
        payload = {
            "uniqueId": unique_id,
        }

        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=self.timeout
            )

            try:
                resp_json = response.json()
            except Exception as e:
                logger.error(f"Invalid JSON in report result response: {e}")
                return {
                    "success": False,
                    "error": "Invalid response format",
                    "error_code": "INVALID_JSON",
                }

            if response.status_code == 200:
                data = resp_json.get("data", {})
                error_obj = resp_json.get("error")
                
                if error_obj:
                    # Error in response body
                    error_message = error_obj.get("message", "Failed to retrieve report")
                    error_code = error_obj.get("code")
                    
                    logger.warning(f"Report retrieval error: {error_message} (code: {error_code})")
                    return {
                        "success": False,
                        "error": error_message,
                        "error_code": error_code or "REPORT_RETRIEVAL_FAILED",
                        "raw": resp_json,
                    }
                
                # Success case - extract report data
                details = data.get("details", {})
                json_data = details.get("jsonData", {})
                score_data = json_data.get("score", {})
                person_info = score_data.get("personInformation", {})
                
                credit_score = score_data.get("score")
                risk_level = score_data.get("risk")
                grade_description = person_info.get("gradeDescription")
                
                logger.info(
                    f"Report retrieved successfully: unique_id={unique_id}, "
                    f"score={credit_score}, risk={risk_level}"
                )
                
                return {
                    "success": True,
                    "report_data": json_data,
                    "score": credit_score,
                    "risk": risk_level,
                    "grade_description": grade_description,
                    "person_info": person_info,
                    "score_codes": score_data.get("scoreCodes", []),
                    "message": data.get("message", "Report retrieved successfully"),
                    "unique_id": resp_json.get("uniqueId"),
                    "timestamp": resp_json.get("timestamp"),
                    "raw": resp_json,
                }
            
            elif response.status_code == 400:
                # Handle validation errors
                try:
                    error_obj = resp_json.get("error", {})
                    error_message = error_obj.get("message", "Validation error")
                    error_code = error_obj.get("code")
                    
                    logger.warning(f"Report result validation error: {error_message} (code: {error_code})")
                    return {
                        "success": False,
                        "error": error_message,
                        "error_code": error_code or "VALIDATION_ERROR",
                        "status": 400,
                        "is_validation_error": True,
                        "raw": resp_json,
                    }
                except Exception:
                    return {
                        "success": False,
                        "error": response.text[:500] if response.text else "Validation failed",
                        "error_code": "VALIDATION_ERROR",
                        "status": 400,
                    }
            else:
                error_body = response.text[:500] if response.text else ""
                logger.error(f"Report retrieval failed: HTTP {response.status_code} | {error_body}")
                return {
                    "success": False,
                    "error": error_body or "Failed to retrieve report",
                    "error_code": "SERVICE_ERROR",
                    "status": response.status_code,
                }

        except requests.exceptions.Timeout:
            logger.error("Report retrieval timeout")
            return {
                "success": False,
                "error": "Request timeout",
                "error_code": "TIMEOUT",
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Report retrieval request failed: {e}")
            return {
                "success": False,
                "error": f"Network error: {str(e)}",
                "error_code": "NETWORK_ERROR",
            }
        except Exception as e:
            logger.error(f"Unexpected error during report retrieval: {e}")
            return {
                "success": False,
                "error": "Unexpected error",
                "error_code": "UNEXPECTED_ERROR",
            }
