# profiles/models/kyc_video_asset.py

import hashlib

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel


class KYCVideoAsset(BaseModel):
    """
    Durable copy of a submitted KYC video with retention policy metadata.
    - 'file' should be stored on a durable storage (S3, etc).
    - 'retention_until' = None means keep indefinitely (infinite retention).
    """
    profile = models.ForeignKey(
        "profiles.Profile",
        on_delete=models.CASCADE,
        related_name="kyc_video_assets",
        verbose_name=_("پروفایل"),
    )
    file = models.FileField(
        upload_to="kyc_videos/%Y/%m/%d/", verbose_name=_("فایل ویدئو")
    )
    sha256 = models.CharField(
        max_length=64, blank=True, null=True, verbose_name=_("هش SHA256")
    )
    size = models.BigIntegerField(default=0, verbose_name=_("حجم (بایت)"))
    is_approved_copy = models.BooleanField(
        default=False, verbose_name=_("نسخهٔ مورد تأیید")
    )
    retention_until = models.DateTimeField(
        blank=True, null=True, verbose_name=_("نگهداشت تا")
    )
    created_by_attempt = models.ForeignKey(
        "profiles.ProfileKYCAttempt",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="video_assets",
        verbose_name=_("ایجاد شده توسط تلاش"),
    )

    # ---------- Factory ----------
    @classmethod
    def create_from_upload(
            cls, *, profile, django_file, storage_prefix: str = None,
            created_by_attempt=None
    ) -> "KYCVideoAsset":
        """
        Persist a durable copy from an uploaded Django file:
        - Streams file to memory for hashing (OK for <= ~50MB per your validator)
        - Saves through default_storage using a prefixed path
        - Returns created KYCVideoAsset with sha256 & size
        """
        # read() is acceptable here given your 50MB validator; if larger, refactor to chunked hashing
        content = django_file.read()
        sha256 = hashlib.sha256(content).hexdigest()
        prefix = (storage_prefix or "kyc_videos/").rstrip("/") + "/"
        filename = f"{prefix}{profile.id}-{django_file.name}"
        path = default_storage.save(filename, ContentFile(content))
        return cls.objects.create(
            profile=profile,
            file=path,
            sha256=sha256,
            size=len(content),
            created_by_attempt=created_by_attempt,
        )

    # ---------- Retention ----------
    def mark_retention(self, days: int | None, approved: bool) -> None:
        """
        Apply retention window. days=None → infinite retention.
        """
        self.is_approved_copy = approved
        self.retention_until = None if days is None else timezone.now() + timezone.timedelta(
            days=days
        )
        self.save(update_fields=["is_approved_copy", "retention_until"])
