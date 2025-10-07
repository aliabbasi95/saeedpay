# profiles/models/kyc_attempt.py

from __future__ import annotations

from typing import Optional

from django.db import models, IntegrityError
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from profiles.models.profile import Profile
from profiles.utils.choices import AttemptType, AttemptStatus


class AttemptAlreadyProcessing(Exception):
    """Raised when a processing attempt of the same type already exists for the profile."""


class ProfileKYCAttempt(BaseModel):
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="kyc_attempts",
        verbose_name=_("پروفایل"),
    )

    attempt_type = models.CharField(
        max_length=32,
        choices=AttemptType.choices,
        db_index=True,
        verbose_name=_("نوع تلاش"),
    )
    status = models.CharField(
        max_length=16,
        choices=AttemptStatus.choices,
        default=AttemptStatus.PENDING,
        db_index=True,
        verbose_name=_("وضعیت"),
    )

    external_id = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_("شناسه خارجی"),
    )
    request_payload = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_("Payload درخواست"),
    )
    response_payload = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_("Payload پاسخ"),
    )

    http_status = models.IntegerField(
        blank=True,
        null=True,
        verbose_name=_("کد HTTP"),
    )
    error_code = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        verbose_name=_("کد خطا"),
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("پیام خطا"),
    )

    retry_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("تعداد تلاش مجدد"),
    )
    started_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("زمان شروع"),
    )
    finished_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("زمان پایان"),
    )

    # ---------- Factory with DB-level uniqueness guard ----------
    @classmethod
    def start_new(
            cls,
            *,
            profile_id: int,
            attempt_type: str,
            request_payload: dict | None = None,
    ) -> "ProfileKYCAttempt":
        """
        Create a new attempt already in PROCESSING state.
        If a PROCESSING attempt (unfinished) of same type exists, raise AttemptAlreadyProcessing.
        """
        try:
            return cls.objects.create(
                profile_id=profile_id,
                attempt_type=attempt_type,
                status=AttemptStatus.PROCESSING,
                started_at=timezone.now(),
                request_payload=request_payload or {},
            )
        except IntegrityError as e:
            # Violates partial unique index (processing & unfinished)
            raise AttemptAlreadyProcessing from e

    # ---------- Mutators ----------
    def mark_success(
            self,
            response_payload: dict | None = None,
            external_id: str | None = None,
            http_status: int | None = None,
    ) -> "ProfileKYCAttempt":
        """Mark attempt as SUCCESS and persist optional fields."""
        self.status = AttemptStatus.SUCCESS
        self.finished_at = timezone.now()
        if response_payload is not None:
            self.response_payload = response_payload
        if external_id:
            self.external_id = external_id
        if http_status is not None:
            self.http_status = http_status
        self.save(
            update_fields=[
                "status",
                "response_payload",
                "external_id",
                "http_status",
                "finished_at",
                "updated_at",
            ]
        )
        return self

    def mark_rejected(
            self,
            response_payload: dict | None = None,
            http_status: int | None = None,
            error_message: str | None = None,
    ) -> "ProfileKYCAttempt":
        """Mark attempt as REJECTED (e.g., business rule) with optional payload."""
        self.status = AttemptStatus.REJECTED
        self.finished_at = timezone.now()
        if response_payload is not None:
            self.response_payload = response_payload
        if http_status is not None:
            self.http_status = http_status
        if error_message:
            self.error_message = error_message
        self.save(
            update_fields=[
                "status",
                "response_payload",
                "http_status",
                "error_message",
                "finished_at",
                "updated_at",
            ]
        )
        return self

    def mark_failed(
            self,
            error_message: str,
            error_code: str | None = None,
            http_status: int | None = None,
            response_payload: dict | None = None,
    ) -> "ProfileKYCAttempt":
        """Mark attempt as FAILED (technical/transport errors)."""
        self.status = AttemptStatus.FAILED
        self.finished_at = timezone.now()
        self.error_message = error_message
        if error_code:
            self.error_code = error_code
        if http_status is not None:
            self.http_status = http_status
        if response_payload is not None:
            self.response_payload = response_payload
        self.save(
            update_fields=[
                "status",
                "error_message",
                "error_code",
                "http_status",
                "response_payload",
                "finished_at",
                "updated_at",
            ]
        )
        return self

    def bump_retry(self) -> "ProfileKYCAttempt":
        """Increment retry counter atomically."""
        self.retry_count = models.F("retry_count") + 1
        self.save(update_fields=["retry_count", "updated_at"])
        self.refresh_from_db(fields=["retry_count"])
        return self

    @property
    def duration_ms(self) -> Optional[int]:
        """Return duration in milliseconds if finished."""
        if self.started_at and self.finished_at:
            return int(
                (self.finished_at - self.started_at).total_seconds() * 1000
            )
        return None

    def __str__(self) -> str:
        return f"{self.profile_id} | {self.attempt_type} | {self.status}"

    class Meta:
        verbose_name = _("تلاش KYC")
        verbose_name_plural = _("تلاش‌های KYC")
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "attempt_type"],
                condition=Q(
                    status=AttemptStatus.PROCESSING, finished_at__isnull=True
                ),
                name="uniq_processing_attempt_per_type_per_profile",
            ),
        ]
        indexes = [
            models.Index(fields=["profile", "attempt_type", "created_at"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["external_id"]),
        ]
