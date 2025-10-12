# credit/models/loan_risk_report.py

from django.db import models
from django.utils import timezone

from credit.utils.choices import LoanReportStatus, LoanRiskLevel
from lib.erp_base.models.base import BaseModel
from profiles.models.profile import Profile


class LoanRiskReport(BaseModel):
    """
    Model to store loan risk assessment reports from external KYC provider.
    
    This model stores the complete credit scoring report including the score,
    risk level, and detailed JSON data from the loan validation service.
    """

    # Relations
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="loan_risk_reports",
        verbose_name="پروفایل"
    )

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=LoanReportStatus.choices,
        default=LoanReportStatus.PENDING,
        verbose_name="وضعیت",
        db_index=True
    )

    # OTP tracking (Stage 1)
    otp_unique_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="شناسه یکتای OTP",
        help_text="Unique ID from OTP send request"
    )
    otp_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="زمان ارسال OTP"
    )

    # Report request tracking (Stage 2)
    report_unique_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        unique=True,
        verbose_name="شناسه یکتای گزارش",
        help_text="Unique ID from report request",
        db_index=True
    )
    report_requested_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="زمان درخواست گزارش"
    )

    # Report data (Stage 3)
    credit_score = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="امتیاز اعتباری",
        db_index=True
    )
    risk_level = models.CharField(
        max_length=20,
        choices=LoanRiskLevel.choices,
        null=True,
        blank=True,
        verbose_name="سطح ریسک",
        db_index=True
    )
    grade_description = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="توضیحات درجه ریسک"
    )

    # Full report data
    report_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name="داده‌های کامل گزارش",
        help_text="Complete JSON report from external service"
    )

    # Person information from report
    national_code = models.CharField(
        max_length=10,
        verbose_name="کد ملی",
        db_index=True
    )
    mobile_number = models.CharField(
        max_length=11,
        verbose_name="شماره موبایل"
    )

    # Additional metadata
    report_timestamp = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="تاریخ و زمان گزارش (از سرویس)"
    )
    report_types = models.JSONField(
        null=True,
        blank=True,
        verbose_name="انواع گزارش",
        help_text="List of report types included (e.g., Base, Score, Tax)"
    )

    # Error tracking
    error_message = models.TextField(
        null=True,
        blank=True,
        verbose_name="پیام خطا"
    )
    error_code = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="کد خطا"
    )

    # Timestamps
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="تاریخ تکمیل"
    )

    def mark_otp_sent(self, unique_id: str) -> None:
        """Mark that OTP has been sent successfully."""
        self.otp_unique_id = unique_id
        self.otp_sent_at = timezone.now()
        self.status = LoanReportStatus.OTP_SENT
        self.save(
            update_fields=["otp_unique_id", "otp_sent_at", "status",
                           "updated_at"]
        )

    def mark_report_requested(self, unique_id: str) -> None:
        """Mark that report has been requested and is in processing."""
        self.report_unique_id = unique_id
        self.report_requested_at = timezone.now()
        self.status = LoanReportStatus.IN_PROCESSING
        self.save(
            update_fields=[
                "report_unique_id",
                "report_requested_at",
                "status",
                "updated_at"
            ]
        )

    def mark_completed(
            self,
            credit_score: int,
            risk_level: str,
            grade_description: str,
            report_data: dict,
            report_timestamp: str = None,
            report_types: list = None
    ) -> None:
        """Mark report as completed with the retrieved data."""
        self.credit_score = credit_score
        self.risk_level = risk_level
        self.grade_description = grade_description
        self.report_data = report_data
        self.report_timestamp = report_timestamp
        self.report_types = report_types
        self.status = LoanReportStatus.COMPLETED
        self.completed_at = timezone.now()
        self.save(
            update_fields=[
                "credit_score",
                "risk_level",
                "grade_description",
                "report_data",
                "report_timestamp",
                "report_types",
                "status",
                "completed_at",
                "updated_at"
            ]
        )

    def mark_failed(self, error_message: str, error_code: str = None) -> None:
        """Mark report as failed with error details."""
        self.status = LoanReportStatus.FAILED
        self.error_message = error_message
        self.error_code = error_code
        self.save(
            update_fields=[
                "status",
                "error_message",
                "error_code",
                "updated_at"
            ]
        )

    def is_otp_valid(self, validity_minutes: int = 2) -> bool:
        """Check if OTP is still valid (within validity period)."""
        if not self.otp_sent_at:
            return False
        expiry_time = self.otp_sent_at + timezone.timedelta(
            minutes=validity_minutes
        )
        return timezone.now() < expiry_time

    def can_request_report(self) -> bool:
        """Check if report can be requested (OTP sent and valid)."""
        return (
                self.status == LoanReportStatus.OTP_SENT
                and self.otp_unique_id
                and self.is_otp_valid()
        )

    def can_check_result(self) -> bool:
        """Check if report result can be checked."""
        return (
                self.status == LoanReportStatus.IN_PROCESSING
                and self.report_unique_id
        )

    @property
    def risk_description(self) -> str:
        """Get human-readable risk description."""
        if self.risk_level:
            return self.get_risk_level_display()
        return "نامشخص"

    @property
    def is_low_risk(self) -> bool:
        """Check if credit risk is low (A1, A2, B1)."""
        return self.risk_level in [LoanRiskLevel.A1, LoanRiskLevel.A2,
                                   LoanRiskLevel.B1]

    @property
    def is_medium_risk(self) -> bool:
        """Check if credit risk is medium (B2, C1, C2)."""
        return self.risk_level in [LoanRiskLevel.B2, LoanRiskLevel.C1,
                                   LoanRiskLevel.C2]

    @property
    def is_high_risk(self) -> bool:
        """Check if credit risk is high (D, E)."""
        return self.risk_level in [LoanRiskLevel.D, LoanRiskLevel.E]

    @classmethod
    def can_user_request_new_report(cls, profile, cooldown_days: int = 30) -> \
            tuple[bool, str, "LoanRiskReport"]:
        """
        Check if user can request a new loan risk report.
        
        Users can only request a new report if:
        - They have no completed report, OR
        - Their last completed report is at least cooldown_days old
        
        Args:
            profile: User's profile
            cooldown_days: Minimum days between reports (default: 30)
            
        Returns:
            Tuple of (can_request: bool, reason: str, last_report: LoanRiskReport or None)
        """
        last_completed_report = cls.objects.filter(
            profile=profile,
            status=LoanReportStatus.COMPLETED
        ).order_by("-completed_at").first()

        if not last_completed_report:
            # No completed report exists, can request
            return True, "No previous report found", None

        # Check if last report is old enough
        cooldown_period = timezone.timedelta(days=cooldown_days)
        time_since_last = timezone.now() - last_completed_report.completed_at

        if time_since_last >= cooldown_period:
            return True, "Cooldown period passed", last_completed_report

        # Calculate remaining time
        remaining_time = cooldown_period - time_since_last
        days_remaining = remaining_time.days
        hours_remaining = remaining_time.seconds // 3600

        if days_remaining > 0:
            reason = f"باید {days_remaining} روز دیگر صبر کنید"
        else:
            reason = f"باید {hours_remaining} ساعت دیگر صبر کنید"

        return False, reason, last_completed_report

    def __str__(self):
        return f"گزارش ریسک وام {self.profile.user.username} - {self.get_status_display()}"

    class Meta:
        db_table = "credit_loan_risk_report"
        verbose_name = "گزارش ریسک وام"
        verbose_name_plural = "گزارش‌های ریسک وام"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["profile", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["credit_score"]),
        ]
