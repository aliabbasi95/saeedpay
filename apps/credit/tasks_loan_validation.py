# apps/credit/tasks_loan_validation.py

import logging

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.credit.models import LoanRiskReport
from apps.credit.utils.choices import LoanReportStatus, LoanRiskLevel
from apps.kyc.services.identity_auth_service import get_identity_auth_service

logger = logging.getLogger(__name__)

# Set cooldown period in seconds
COOLDOWN_PERIOD = getattr(
    settings, "LOAN_VALIDATION_COOLDOWN_PERIOD", 30 * 24 * 60 * 60
)
REPORT_RETRY_DELAY = getattr(settings, "LOAN_VALIDATION_REPORT_RETRY_DELAY", 15)
REPORT_MAX_RETRIES = getattr(settings, "LOAN_VALIDATION_REPORT_MAX_RETRIES", 24)
OTP_CACHE_TTL = getattr(settings, "LOAN_VALIDATION_OTP_CACHE_TTL", 15 * 60)


def _otp_cache_key(report_id: int) -> str:
    return f"loan-validation:otp:{report_id}"


def _cache_report_otp(report_id: int, otp_code: str) -> bool:
    try:
        cache.set(_otp_cache_key(report_id), str(otp_code), timeout=OTP_CACHE_TTL)
        return True
    except Exception:
        logger.exception("loan.otp_cache.set_failed | report_id=%s", report_id)
        return False


def _get_cached_report_otp(report_id: int) -> str | None:
    try:
        value = cache.get(_otp_cache_key(report_id))
    except Exception:
        logger.exception("loan.otp_cache.get_failed | report_id=%s", report_id)
        return None
    return str(value) if value not in (None, "") else None


def _clear_cached_report_otp(report_id: int) -> None:
    try:
        cache.delete(_otp_cache_key(report_id))
    except Exception:
        logger.exception("loan.otp_cache.delete_failed | report_id=%s", report_id)


def _normalize_risk_level(value) -> str:
    risk = str(value or "").strip().upper()
    return risk if risk in LoanRiskLevel.values else LoanRiskLevel.UNKNOWN


def _risk_description(risk_level: str, provider_description: str | None) -> str | None:
    if provider_description:
        return provider_description
    if risk_level == LoanRiskLevel.UNKNOWN:
        return None
    try:
        return str(LoanRiskLevel(risk_level).label)
    except ValueError:
        return None


def _complete_report(report_id: int, result: dict) -> dict:
    credit_score = result.get("score")
    risk_level = _normalize_risk_level(result.get("risk"))
    grade_description = _risk_description(
        risk_level, result.get("grade_description")
    )
    report_data = result.get("report_data") or {}
    report_timestamp = result.get("timestamp")
    report_types = result.get("report_types")

    with transaction.atomic():
        try:
            report = LoanRiskReport.objects.select_for_update().get(id=report_id)
        except LoanRiskReport.DoesNotExist:
            logger.error(
                "loan.complete | report_id=%s disappeared before save", report_id
            )
            _clear_cached_report_otp(report_id)
            return {"success": False, "error": "report_not_found_after_service"}

        if report.status == LoanReportStatus.COMPLETED:
            _clear_cached_report_otp(report_id)
            return {
                "success": True,
                "report_id": report_id,
                "credit_score": report.credit_score,
                "risk_level": report.risk_level,
                "grade_description": report.grade_description,
                "message": "گزارش قبلاً تکمیل شده است",
            }

        if report.status != LoanReportStatus.IN_PROCESSING:
            _clear_cached_report_otp(report_id)
            return {
                "success": False,
                "report_id": report_id,
                "error": "invalid_report_state",
            }

        report.mark_completed(
            credit_score=credit_score,
            risk_level=risk_level,
            grade_description=grade_description,
            report_data=report_data,
            report_timestamp=report_timestamp,
            report_types=report_types,
        )

    _clear_cached_report_otp(report_id)
    logger.info(
        "loan.complete | report_id=%s completed score=%s risk=%s",
        report_id,
        credit_score,
        risk_level,
    )
    return {
        "success": True,
        "report_id": report_id,
        "credit_score": credit_score,
        "risk_level": risk_level,
        "grade_description": grade_description,
        "message": "گزارش با موفقیت دریافت شد",
    }


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
            report.mark_failed(
                error_message="کد ملی و شماره موبایل الزامی است",
                error_code="MISSING_REQUIRED_FIELDS",
            )
            return {
                "success": False,
                "error": "missing_required_fields",
                "message": "کد ملی و شماره موبایل الزامی است",
                "report_id": report.id,
            }

        # Check cooldown period (30 days between reports)
        can_request, reason, last_report = LoanRiskReport.can_user_request_new_report(
            profile
        )
        if not can_request:
            last_report_date = (
                last_report.completed_at.strftime("%Y/%m/%d") if last_report else ""
            )
            error_message = (
                f"شما قبلاً در تاریخ {last_report_date} گزارش دریافت کرده‌اید. {reason}."
            )
            logger.warning(f"Report {report_id}: Cooldown period not met. {reason}")
            report.mark_failed(
                error_message=error_message, error_code="COOLDOWN_ACTIVE"
            )
            return {
                "success": False,
                "error": "cooldown_period_active",
                "message": error_message,
                "last_report_date": last_report.completed_at.isoformat()
                if last_report
                else None,
                "last_report_id": last_report.id if last_report else None,
                "report_id": report.id,
            }

        # Check if any OTP was sent within the last 2 minutes for this profile
        recent_otp_time = timezone.now() - timezone.timedelta(minutes=2)
        recent_otp_report = (
            LoanRiskReport.objects.filter(
                profile=profile, otp_sent_at__gte=recent_otp_time
            )
            .exclude(id=report.id)
            .first()
        )

        if recent_otp_report:
            time_since_otp = timezone.now() - recent_otp_report.otp_sent_at
            remaining_seconds = int(
                (timezone.timedelta(minutes=2) - time_since_otp).total_seconds()
            )
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
        existing_in_process = (
            LoanRiskReport.objects.filter(
                profile=profile, status=LoanReportStatus.IN_PROCESSING
            )
            .exclude(id=report.id)
            .first()
        )
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
            national_code=profile.national_id, mobile_number=profile.phone_number
        )
    except Exception as e:
        logger.error(f"Failed to send loan OTP for report {report_id}: {e}")
        report.mark_failed(error_message=str(e), error_code="SERVICE_ERROR")
        return {
            "success": False,
            "error": "service_error",
            "message": str(e),
            "report_id": report.id,
        }

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
    """Verify OTP, request the report, and preserve polling context server-side."""
    with transaction.atomic():
        try:
            report = LoanRiskReport.objects.select_for_update().get(id=report_id)
        except LoanRiskReport.DoesNotExist:
            logger.error("loan.verify_otp | report_id=%s not found", report_id)
            return {"success": False, "error": "report_not_found"}

        if not report.can_request_report():
            msg = "گزارش در وضعیت مناسب برای ارسال کد نیست یا کد منقضی شده است"
            logger.warning("loan.verify_otp | report_id=%s invalid_state", report_id)
            return {"success": False, "error": "invalid_report_state", "message": msg}

        otp_unique_id = report.otp_unique_id

    service = get_identity_auth_service()
    try:
        result = service.loan_verify_otp_and_request_report(
            otp_code=otp_code, unique_id=otp_unique_id
        )
    except Exception as exc:
        logger.exception("loan.verify_otp | report_id=%s service_error", report_id)
        report.mark_failed(error_message=str(exc), error_code="SERVICE_ERROR")
        _clear_cached_report_otp(report_id)
        return {"success": False, "error": "service_error", "message": str(exc)}

    if result.get("success"):
        new_unique_id = result.get("unique_id") or otp_unique_id

        if not _cache_report_otp(report_id, otp_code):
            report.mark_failed(
                error_message="امکان نگهداری موقت اطلاعات پیگیری گزارش وجود ندارد",
                error_code="OTP_CACHE_ERROR",
            )
            return {
                "success": False,
                "report_id": report_id,
                "error": "otp_cache_error",
                "message": "خطای موقت در آماده سازی گزارش",
            }

        report.mark_report_requested(new_unique_id)
        logger.info(
            "loan.verify_otp | report_id=%s requested unique_id=%s completed=%s",
            report_id,
            new_unique_id,
            result.get("completed", False),
        )

        if result.get("completed"):
            return _complete_report(report_id, result)

        check_loan_report_result.apply_async(
            args=[report_id],
            countdown=REPORT_RETRY_DELAY,
        )

        return {
            "success": True,
            "report_id": report.id,
            "unique_id": new_unique_id,
            "message": result.get("message", "درخواست گزارش با موفقیت ثبت شد"),
        }

    error_msg = result.get("error", "Failed to verify OTP")
    error_code = result.get("error_code")
    is_otp_error = result.get("is_otp_error", False)
    _clear_cached_report_otp(report_id)
    with transaction.atomic():
        try:
            report = LoanRiskReport.objects.select_for_update().get(id=report_id)
            if is_otp_error and ("منقضی" in (error_msg or "")):
                report.mark_expired(error_message=error_msg, error_code=error_code)
            else:
                report.mark_failed(error_message=error_msg, error_code=error_code)
        except LoanRiskReport.DoesNotExist:
            pass
    logger.warning("loan.verify_otp | report_id=%s failed: %s", report_id, error_msg)
    return {
        "success": False,
        "report_id": report_id,
        "error": "otp_verification_failed",
        "message": error_msg,
    }


@shared_task(bind=True, max_retries=REPORT_MAX_RETRIES)
def check_loan_report_result(self, report_id: int) -> dict:
    """Poll the provider until the structured loan report reaches DONE."""
    with transaction.atomic():
        try:
            report = LoanRiskReport.objects.select_for_update().get(id=report_id)
        except LoanRiskReport.DoesNotExist:
            logger.error("loan.check_result | report_id=%s not found", report_id)
            _clear_cached_report_otp(report_id)
            return {"success": False, "error": "report_not_found"}

        if not report.can_check_result():
            error_msg = "گزارش در وضعیت مناسب برای دریافت نتیجه نیست"
            logger.warning(
                "loan.check_result | report_id=%s invalid_state", report_id
            )
            return {
                "success": False,
                "error": "invalid_report_state",
                "message": error_msg,
            }
        report_unique_id = report.report_unique_id

    otp_code = _get_cached_report_otp(report_id)
    if not otp_code:
        error_msg = "اطلاعات موقت پیگیری گزارش منقضی شده است؛ لطفا درخواست جدید ثبت کنید"
        with transaction.atomic():
            try:
                report = LoanRiskReport.objects.select_for_update().get(id=report_id)
            except LoanRiskReport.DoesNotExist:
                return {"success": False, "error": "report_not_found"}

            if report.status == LoanReportStatus.COMPLETED:
                return {
                    "success": True,
                    "report_id": report_id,
                    "credit_score": report.credit_score,
                    "risk_level": report.risk_level,
                    "grade_description": report.grade_description,
                    "message": "گزارش قبلاً تکمیل شده است",
                }

            if report.status == LoanReportStatus.IN_PROCESSING:
                report.mark_failed(
                    error_message=error_msg,
                    error_code="OTP_CONTEXT_EXPIRED",
                )

        return {
            "success": False,
            "report_id": report_id,
            "error": "otp_context_expired",
            "message": error_msg,
        }

    service = get_identity_auth_service()
    try:
        result = service.loan_get_report_result(
            unique_id=report_unique_id,
            otp_code=otp_code,
        )
    except Exception as exc:
        result = {
            "success": False,
            "error": str(exc),
            "error_code": "SERVICE_ERROR",
            "retryable": True,
        }

    if result.get("success") and result.get("completed"):
        return _complete_report(report_id, result)

    if result.get("success") and not result.get("completed"):
        if self.request.retries < self.max_retries:
            logger.info(
                "loan.check_result | report_id=%s processing status=%s retry=%s/%s",
                report_id,
                result.get("status"),
                self.request.retries + 1,
                self.max_retries,
            )
            raise self.retry(countdown=REPORT_RETRY_DELAY)

        error_msg = "زمان انتظار برای آماده شدن گزارش به پایان رسید"
        error_code = "REPORT_PROCESSING_TIMEOUT"
    else:
        error_msg = result.get("error", "Failed to get report")
        error_code = result.get("error_code") or "REPORT_RETRIEVAL_FAILED"
        if result.get("retryable") and self.request.retries < self.max_retries:
            logger.warning(
                "loan.check_result | report_id=%s retryable_error=%s retry=%s/%s",
                report_id,
                error_code,
                self.request.retries + 1,
                self.max_retries,
            )
            raise self.retry(countdown=REPORT_RETRY_DELAY)

    with transaction.atomic():
        try:
            report = LoanRiskReport.objects.select_for_update().get(id=report_id)
        except LoanRiskReport.DoesNotExist:
            report = None

        if report and report.status == LoanReportStatus.IN_PROCESSING:
            report.mark_failed(error_message=error_msg, error_code=error_code)
        elif report and report.status == LoanReportStatus.COMPLETED:
            _clear_cached_report_otp(report_id)
            return {
                "success": True,
                "report_id": report_id,
                "credit_score": report.credit_score,
                "risk_level": report.risk_level,
                "grade_description": report.grade_description,
                "message": "گزارش قبلاً تکمیل شده است",
            }
    _clear_cached_report_otp(report_id)
    logger.warning(
        "loan.check_result | report_id=%s failed code=%s message=%s",
        report_id,
        error_code,
        error_msg,
    )
    return {
        "success": False,
        "report_id": report_id,
        "error": "report_retrieval_failed",
        "message": error_msg,
    }
