# profiles/models/profile.py

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from lib.erp_base.validators import validate_national_id
from profiles.utils.choices import AuthenticationStage, KYCStatus


class Profile(BaseModel):
    user = models.OneToOneField(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name=_("کاربر"),
    )
    phone_number = models.CharField(
        max_length=11,
        unique=True,
        validators=[RegexValidator(
            r"^09\d{9}$", _("باید با 09 شروع شده و 11 رقم باشد")
        )],
        verbose_name=_("شماره موبایل"),
    )
    email = models.EmailField(blank=True, verbose_name=_("ایمیل"))
    national_id = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        validators=[validate_national_id],
        verbose_name=_("کد ملی"),
    )
    first_name = models.CharField(
        blank=True,
        max_length=255,
        verbose_name=_("نام"),
    )
    last_name = models.CharField(
        blank=True,
        max_length=255,
        verbose_name=_("نام خانوادگی"),
    )
    birth_date = models.CharField(
        max_length=10,
        null=True,
        blank=False,
        validators=[RegexValidator(
            r"\d\d\d\d\/\d\d\/\d\d", _("فرمت باید YYYY/MM/DD باشد")
        )],
        help_text=_("فرمت: YYYY/MM/DD"),
        verbose_name=_("تاریخ تولد"),
    )

    # Explicit authentication stage and status
    auth_stage = models.PositiveSmallIntegerField(
        choices=AuthenticationStage.choices,
        default=AuthenticationStage.SIGNUP,
        verbose_name=_("مرحله احراز هویت"),
    )
    kyc_status = models.CharField(
        max_length=10,
        choices=KYCStatus.choices,
        null=True,
        blank=True,
        default=None,
        verbose_name=_("وضعیت KYC"),
    )
    video_task_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        verbose_name=_("شناسه تسک ویدئو"),
    )
    kyc_last_checked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("آخرین زمان بررسی KYC"),
    )

    # Phone/National match status (Shahkar)
    phone_national_id_match_status = models.CharField(
        max_length=10,
        choices=KYCStatus.choices,
        null=True,
        blank=True,
        default=None,
        verbose_name=_("نتیجه شاهکار (تطابق موبایل/کدملی)"),
    )

    # Timestamps
    identity_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("زمانی که احراز هویت شاهکار با موفقیت انجام شد"),
        verbose_name=_("زمان تایید هویت"),
    )
    video_submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("زمان ارسال ویدئو برای احراز ویدئویی"),
        verbose_name=_("زمان ارسال ویدئو"),
    )
    video_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("زمان ثبت نتیجه نهایی بررسی ویدئویی (قبول/رد)"),
        verbose_name=_("زمان اتمام بررسی ویدئو"),
    )

    # -----------------------
    # Derived / utility props
    # -----------------------
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return f"پروفایل {self.user.username}"

    # -----------------------
    # Flow guards
    # -----------------------
    def can_submit_video_kyc(self) -> bool:
        """User can submit video only in IDENTITY_VERIFIED stage."""
        return (
                self.auth_stage == AuthenticationStage.IDENTITY_VERIFIED
                and self.kyc_status != KYCStatus.PROCESSING
        )

    def is_video_kyc_in_progress(self) -> bool:
        """Video KYC is in progress if stage=IDENTITY_VERIFIED and status=PROCESSING."""
        return (
                self.auth_stage == AuthenticationStage.IDENTITY_VERIFIED
                and self.kyc_status == KYCStatus.PROCESSING
        )

    def has_valid_video_task(self) -> bool:
        return bool(self.video_task_id and self.video_task_id.strip())

    # -----------------------
    # State transitions (single source of truth)
    # -----------------------
    # Identity (Shahkar)
    def begin_phone_national_id_check(self) -> None:
        """Mark Shahkar check as processing (pre-call guard)."""
        self.phone_national_id_match_status = KYCStatus.PROCESSING
        self.save(
            update_fields=["phone_national_id_match_status", "updated_at"]
        )

    def mark_phone_national_id_failed(self) -> None:
        """Validation/format error in Shahkar inputs."""
        self.phone_national_id_match_status = KYCStatus.FAILED
        self.save(
            update_fields=["phone_national_id_match_status", "updated_at"]
        )

    def mark_phone_national_id_rejected(self) -> None:
        """Shahkar says not matched."""
        self.phone_national_id_match_status = KYCStatus.REJECTED
        self.save(
            update_fields=["phone_national_id_match_status", "updated_at"]
        )

    def mark_identity_verified(self) -> None:
        """Shahkar matched => identity verified stage and grant default credit limit."""
        from credit.services.credit_limit_service import \
            grant_default_credit_limit  # local import to avoid cycles

        self.auth_stage = AuthenticationStage.IDENTITY_VERIFIED
        self.kyc_status = None
        self.phone_national_id_match_status = KYCStatus.ACCEPTED
        self.identity_verified_at = timezone.now()
        self.save(
            update_fields=[
                "auth_stage",
                "kyc_status",
                "phone_national_id_match_status",
                "identity_verified_at",
                "updated_at",
            ]
        )

        # Make credit limit creation idempotent and post-commit safe
        transaction.on_commit(
            lambda: grant_default_credit_limit(user=self.user)
        )

    # Video KYC
    def mark_video_submitted(
            self, task_id: str | None = None, save: bool = True
    ) -> None:
        """Move to VIDEO_VERIFIED stage with PROCESSING status + set task id."""
        if not self.can_submit_video_kyc():
            raise ValidationError(
                _(
                    "در این مرحله امکان ارسال ویدئو وجود ندارد؛ باید در مرحله «تایید هویت» باشید."
                )
            )
        self.kyc_status = KYCStatus.PROCESSING
        self.video_submitted_at = timezone.now()

        update_fields = ["auth_stage", "kyc_status", "video_submitted_at",
                         "updated_at"]
        if task_id:
            if len(task_id.strip()) > 64:
                raise ValidationError(
                    _("طول شناسه تسک ویدئو نباید از ۶۴ کاراکتر بیشتر باشد")
                )
            self.video_task_id = task_id
            update_fields.append("video_task_id")

        if save:
            self.save(update_fields=update_fields)

    def update_kyc_result(
            self, accepted: bool, error_details: str | None = None
    ) -> None:
        """Finalize KYC result for current attempt."""
        now = timezone.now()
        self.kyc_last_checked_at = now
        self.video_verified_at = now

        if accepted:
            self.auth_stage = AuthenticationStage.VIDEO_VERIFIED
            self.kyc_status = KYCStatus.ACCEPTED
        elif error_details and "rejected" in error_details.lower():
            self.kyc_status = KYCStatus.REJECTED
        else:
            self.kyc_status = KYCStatus.FAILED

        self.save(
            update_fields=["kyc_last_checked_at", "kyc_status",
                           "video_verified_at", "updated_at"]
        )

    def reset_to_identity_verified(self) -> None:
        """Rollback video path to allow retry."""
        self.auth_stage = AuthenticationStage.IDENTITY_VERIFIED
        self.kyc_status = None
        self.video_task_id = None
        self.video_submitted_at = None
        self.video_verified_at = None
        self.save(
            update_fields=[
                "auth_stage",
                "kyc_status",
                "video_task_id",
                "video_submitted_at",
                "video_verified_at",
                "updated_at",
            ]
        )

    def can_retry_video_kyc(self) -> bool:
        return self.auth_stage == AuthenticationStage.IDENTITY_VERIFIED and self.kyc_status in [
            KYCStatus.FAILED,
            KYCStatus.REJECTED,
        ]

    def get_kyc_status_display_info(self) -> dict:
        return {
            "status": self.kyc_status,
            "stage": self.auth_stage,
            "can_submit": self.can_submit_video_kyc(),
            "can_retry": self.can_retry_video_kyc(),
            "in_progress": self.is_video_kyc_in_progress(),
            "has_task": self.has_valid_video_task(),
            "last_checked": self.kyc_last_checked_at.isoformat() if self.kyc_last_checked_at else None,
        }

    def touch_kyc_check(self) -> None:
        self.kyc_last_checked_at = timezone.localtime(timezone.now())
        self.save(update_fields=["kyc_last_checked_at", "updated_at"])

    class Meta:
        verbose_name = _("پروفایل")
        verbose_name_plural = _("پروفایل‌ها")
        constraints = [
            models.UniqueConstraint(
                fields=["national_id"],
                name="unique_national_id_not_null",
                condition=models.Q(national_id__isnull=False),
            )
        ]
        indexes = [
            models.Index(fields=["auth_stage"]),
            models.Index(fields=["kyc_status"]),
            models.Index(fields=["phone_national_id_match_status"]),
            models.Index(fields=["video_task_id"]),
        ]
