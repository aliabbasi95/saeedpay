# profiles/models/kyc_attempt.py

from __future__ import annotations

import uuid
from typing import Optional

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from profiles.models.profile import Profile
from profiles.utils.choices import AttemptType, AttemptStatus


class ProfileKYCAttempt(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="kyc_attempts"
    )

    attempt_type = models.CharField(
        max_length=32, choices=AttemptType.choices, db_index=True
    )
    status = models.CharField(
        max_length=16,
        choices=AttemptStatus.choices,
        default=AttemptStatus.PENDING,
        db_index=True,
    )

    external_id = models.CharField(
        max_length=128, blank=True, null=True, db_index=True
    )

    request_payload = models.JSONField(blank=True, null=True)
    response_payload = models.JSONField(blank=True, null=True)

    http_status = models.IntegerField(blank=True, null=True)
    error_code = models.CharField(max_length=64, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    retry_count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = _("KYC attempt")
        verbose_name_plural = _("KYC attempts")
        indexes = [
            models.Index(fields=["profile", "attempt_type", "created_at"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["external_id"]),
        ]

    # ---------- Helper methods ----------
    def start(
            self, request_payload: dict | None = None
    ) -> "ProfileKYCAttempt":
        self.status = AttemptStatus.PROCESSING
        if request_payload is not None:
            self.request_payload = request_payload
        self.started_at = timezone.now()
        self.save(
            update_fields=["status", "request_payload", "started_at",
                           "updated_at"]
        )
        return self

    def mark_success(
            self,
            response_payload: dict | None = None,
            external_id: str | None = None,
            http_status: int | None = None,
    ) -> "ProfileKYCAttempt":
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
                "status", "response_payload", "external_id", "http_status",
                "finished_at", "updated_at"
            ]
        )
        return self

    def mark_rejected(
            self,
            response_payload: dict | None = None,
            http_status: int | None = None,
            error_message: str | None = None,
    ) -> "ProfileKYCAttempt":
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
                "status", "response_payload", "http_status", "error_message",
                "finished_at", "updated_at"
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
                "status", "error_message", "error_code", "http_status",
                "response_payload",
                "finished_at", "updated_at"
            ]
        )
        return self

    def bump_retry(self) -> "ProfileKYCAttempt":
        self.retry_count = models.F("retry_count") + 1
        self.save(update_fields=["retry_count", "updated_at"])
        self.refresh_from_db(fields=["retry_count"])
        return self

    @property
    def duration_ms(self) -> Optional[int]:
        if self.started_at and self.finished_at:
            return int(
                (self.finished_at - self.started_at).total_seconds() * 1000
            )
        return None

    def __str__(self) -> str:
        return f"{self.profile_id} | {self.attempt_type} | {self.status}"
