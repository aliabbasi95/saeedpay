# credit/tasks_loan_validation.py

import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from credit.models import LoanRiskReport
from credit.utils.choices import LoanReportStatus
from profiles.models.profile import Profile
from kyc.services.identity_auth_service import get_identity_auth_service

logger = logging.getLogger(__name__)

# Set cooldown period in seconds
COOLDOWN_PERIOD = getattr(settings, 'LOAN_VALIDATION_COOLDOWN_PERIOD', 30 * 24 * 60 * 60)
@shared_task(bind=True)
def send_loan_validation_otp(self, report_id: int) -> dict:
    """
    Task to send OTP for loan validation (Stage 1).
    
    Creates a new LoanRiskReport record and sends OTP to user's mobile.
    
    Args:
        report_id: ID of the LoanRiskReport to update
        
    Returns:
        Dict with success status and report_id
    """
    with transaction.atomic():
        try:
            report = LoanRiskReport.objects.select_for_update().get(id=report_id)
        except LoanRiskReport.DoesNotExist:
            logger.error(f"LoanRiskReport {report_id} not found")
            return {"success": False, "error": "report_not_found"}
        profile = report.profile

        # Validate required fields
        if not profile.national_id or not profile.phone_number:
            logger.warning(f"Report {report_id}: Missing national_id or phone_number")
            report.mark_failed(error_message="کد ملی و شماره موبایل الزامی است", error_code="MISSING_REQUIRED_FIELDS")
            return {
                "success": False,
                "error": "missing_required_fields",
                "message": "کد ملی و شماره موبایل الزامی است",
                "report_id": report.id,
            }

        # Check cooldown period (30 days between reports)
        can_request, reason, last_report = LoanRiskReport.can_user_request_new_report(profile)
        if not can_request:
            last_report_date = last_report.completed_at.strftime('%Y/%m/%d') if last_report else ''
            error_message = f"شما قبلاً در تاریخ {last_report_date} گزارش دریافت کرده‌اید. {reason}."
            logger.warning(f"Report {report_id}: Cooldown period not met. {reason}")
            report.mark_failed(error_message=error_message, error_code="COOLDOWN_ACTIVE")
            return {
                "success": False,
                "error": "cooldown_period_active",
                "message": error_message,
                "last_report_date": last_report.completed_at.isoformat() if last_report else None,
                "last_report_id": last_report.id if last_report else None,
                "report_id": report.id,
            }

        # Check if any OTP was sent within the last 2 minutes for this profile
        recent_otp_time = timezone.now() - timezone.timedelta(minutes=2)
        recent_otp_report = LoanRiskReport.objects.filter(
            profile=profile,
            otp_sent_at__gte=recent_otp_time
        ).exclude(id=report.id).first()

        if recent_otp_report:
            time_since_otp = timezone.now() - recent_otp_report.otp_sent_at
            remaining_seconds = int((timezone.timedelta(minutes=2) - time_since_otp).total_seconds())
            logger.warning(
                f"Report {report_id}: OTP requested too frequently. "
                f"Last OTP sent {time_since_otp.total_seconds():.0f} seconds ago. "
                f"Must wait {remaining_seconds} more seconds."
            )
            return {
                "success": False,
                "error": "otp_request_too_frequent",
                "message": f"برای درخواست مجدد کد باید {remaining_seconds} ثانیه صبر کنید.",
                "wait_seconds": remaining_seconds,
                "report_id": report.id,
            }

        # If another report is in processing, don't allow new request
        existing_in_process = LoanRiskReport.objects.filter(
            profile=profile,
            status=LoanReportStatus.IN_PROCESSING
        ).exclude(id=report.id).first()
        if existing_in_process:
            logger.warning(
                f"Report {report_id}: Report {existing_in_process.id} is already in processing"
            )
            return {
                "success": False,
                "error": "report_in_progress",
                "message": "گزارش قبلی شما هنوز در حال پردازش است. لطفا صبر کنید.",
                "report_id": existing_in_process.id,
            }
    
    # Send OTP through service
    service = get_identity_auth_service()
    try:
        result = service.loan_send_otp(
            national_code=profile.national_id,
            mobile_number=profile.phone_number
        )
    except Exception as e:
        logger.error(f"Failed to send loan OTP for report {report_id}: {e}")
        report.mark_failed(error_message=str(e), error_code="SERVICE_ERROR")
        return {"success": False, "error": "service_error", "message": str(e), "report_id": report.id}
    
    # Update report based on result
    if result.get("success"):
        unique_id = result.get("unique_id")
        report.mark_otp_sent(unique_id)
        logger.info(f"Loan OTP sent successfully for report {report.id}")
        return {
            "success": True,
            "report_id": report.id,
            "unique_id": unique_id,
            "message": result.get("message", "کد با موفقیت ارسال شد"),
        }
    else:
        error_msg = result.get("error", "Failed to send OTP")
        error_code = result.get("error_code")
        report.mark_failed(error_message=error_msg, error_code=error_code)
        logger.warning(f"Failed to send loan OTP for report {report_id}: {error_msg}")
        return {
            "success": False,
            "report_id": report.id,
            "error": "otp_send_failed",
            "message": error_msg,
        }


@shared_task(bind=True)
def verify_loan_otp_and_request_report(self, report_id: int, otp_code: str) -> dict:
    """
    Task to verify OTP and request loan validation report (Stage 2).
    
    Args:
        report_id: ID of the LoanRiskReport
        otp_code: OTP code provided by user
        
    Returns:
        Dict with success status and new unique_id for tracking
    """
    try:
        report = LoanRiskReport.objects.select_for_update().get(id=report_id)
    except LoanRiskReport.DoesNotExist:
        logger.error(f"LoanRiskReport {report_id} not found")
        return {"success": False, "error": "report_not_found"}
    
    # Validate report state
    if not report.can_request_report():
        error_msg = "گزارش در وضعیت مناسب برای ارسال کد نیست یا کد منقضی شده است"
        logger.warning(f"Report {report_id} cannot request report: {error_msg}")
        return {
            "success": False,
            "error": "invalid_report_state",
            "message": error_msg,
        }
    
    # Verify OTP and request report
    service = get_identity_auth_service()
    try:
        result = service.loan_verify_otp_and_request_report(
            otp_code=otp_code,
            unique_id=report.otp_unique_id
        )
    except Exception as e:
        logger.error(f"Failed to verify OTP for report {report_id}: {e}")
        report.mark_failed(error_message=str(e), error_code="SERVICE_ERROR")
        return {"success": False, "error": "service_error", "message": str(e)}
    
    # Update report based on result
    if result.get("success"):
        new_unique_id = result.get("unique_id")
        report.mark_report_requested(new_unique_id)
        logger.info(f"Report requested successfully for report {report_id}, unique_id: {new_unique_id}")
        
        # Automatically trigger checking the result after a delay
        check_loan_report_result.apply_async(
            args=[report_id],
            countdown=5  # Check after 5 seconds
        )
        
        return {
            "success": True,
            "report_id": report.id,
            "unique_id": new_unique_id,
            "message": result.get("message", "درخواست گزارش با موفقیت ثبت شد"),
        }
    else:
        error_msg = result.get("error", "Failed to verify OTP")
        error_code = result.get("error_code")
        
        # Check if OTP expired
        if result.get("is_otp_error") and "منقضی" in error_msg:
            report.status = LoanReportStatus.EXPIRED
            report.error_message = error_msg
            report.error_code = error_code
            report.save(update_fields=['status', 'error_message', 'error_code', 'updated_at'])
        else:
            report.mark_failed(error_message=error_msg, error_code=error_code)
        
        logger.warning(f"Failed to verify OTP for report {report_id}: {error_msg}")
        return {
            "success": False,
            "report_id": report.id,
            "error": "otp_verification_failed",
            "message": error_msg,
        }


@shared_task(bind=True, max_retries=5)
def check_loan_report_result(self, report_id: int) -> dict:
    """
    Task to check loan validation report result (Stage 3).
    
    This task will retry if the report is still processing.
    
    Args:
        report_id: ID of the LoanRiskReport
        
    Returns:
        Dict with success status and report data
    """
    try:
        report = LoanRiskReport.objects.select_for_update().get(id=report_id)
    except LoanRiskReport.DoesNotExist:
        logger.error(f"LoanRiskReport {report_id} not found")
        return {"success": False, "error": "report_not_found"}
    
    # Validate report state
    if not report.can_check_result():
        error_msg = "گزارش در وضعیت مناسب برای دریافت نتیجه نیست"
        logger.warning(f"Report {report_id} cannot check result: {error_msg}")
        return {
            "success": False,
            "error": "invalid_report_state",
            "message": error_msg,
        }
    
    # Get report result
    service = get_identity_auth_service()
    try:
        result = service.loan_get_report_result(unique_id=report.report_unique_id)
    except Exception as e:
        # Network error - retry
        retry_delay = 10  # 10 seconds
        if self.request.retries < self.max_retries:
            logger.warning(f"Report {report_id}: Service error, retrying: {e}")
            raise self.retry(exc=e, countdown=retry_delay)
        
        logger.error(f"Report {report_id}: Service error after max retries: {e}")
        report.mark_failed(error_message=str(e), error_code="SERVICE_ERROR")
        return {"success": False, "error": "service_error", "message": str(e)}
    
    # Update report based on result
    if result.get("success"):
        # Report is ready
        credit_score = result.get("score")
        risk_level = result.get("risk")
        grade_description = result.get("grade_description")
        report_data = result.get("report_data")
        report_timestamp = result.get("timestamp")
        
        # Extract report types if available
        report_types = report_data.get("reportTypes") if report_data else None
        
        report.mark_completed(
            credit_score=credit_score,
            risk_level=risk_level,
            grade_description=grade_description,
            report_data=report_data,
            report_timestamp=report_timestamp,
            report_types=report_types
        )
        
        logger.info(
            f"Report {report_id} completed successfully: score={credit_score}, risk={risk_level}"
        )
        return {
            "success": True,
            "report_id": report.id,
            "credit_score": credit_score,
            "risk_level": risk_level,
            "grade_description": grade_description,
            "message": "گزارش با موفقیت دریافت شد",
        }
    else:
        error_msg = result.get("error", "Failed to get report")
        error_code = result.get("error_code")
        
        # If still processing, retry
        if "processing" in error_msg.lower() or "در حال پردازش" in error_msg:
            retry_delay = 10  # 10 seconds
            if self.request.retries < self.max_retries:
                logger.info(f"Report {report_id} still processing, will retry")
                raise self.retry(countdown=retry_delay)
        
        # Failed permanently
        report.mark_failed(error_message=error_msg, error_code=error_code)
        logger.warning(f"Report {report_id} failed: {error_msg}")
        return {
            "success": False,
            "report_id": report.id,
            "error": "report_retrieval_failed",
            "message": error_msg,
        }
