# kyc/api/public/v1/serializers/video_verification.py

from rest_framework import serializers
import re

_DATE_RE = re.compile(r"^\d{4}/\d{2}/\d{2}$")
_ALLOWED_EXTS = (".mp4", ".mov", ".avi", ".mkv")
_ALLOWED_CT_PREFIXES = ("video/",)


class VideoVerificationSubmitSerializer(serializers.Serializer):
    """
    Serializer for video verification submission requests.
    """
    national_id = serializers.CharField(
        max_length=10,
        required=True,
        help_text="Iranian national ID (10 digits)"
    )
    birth_date = serializers.CharField(
        max_length=10,
        required=True,
        help_text="Birth date in format YYYY/MM/DD"
    )
    selfie_video = serializers.FileField(
        required=True,
        help_text="Selfie video file for verification"
    )
    rand_action = serializers.CharField(
        max_length=50,
        required=True,
        help_text="Random action string for verification"
    )
    matching_thr = serializers.IntegerField(
        required=False,
        help_text="Facial matching threshold (optional)"
    )
    liveness_thr = serializers.IntegerField(
        required=False,
        help_text="Liveness detection threshold (optional)"
    )

    def validate_national_id(self, value):
        v = (value or "").strip()
        if not v.isdigit() or len(v) != 10:
            raise serializers.ValidationError(
                "Invalid national ID format. Must be 10 digits."
                )
        return v

    def validate_birth_date(self, value):
        v = (value or "").strip()
        if not _DATE_RE.match(v):
            raise serializers.ValidationError(
                "Invalid birth date format. Must be YYYY/MM/DD."
                )
        # normalize to YYYYMMDD for provider
        return v.replace("/", "")

    def validate_selfie_video(self, value):
        name_ok = any(
            value.name.lower().endswith(ext) for ext in _ALLOWED_EXTS
            )
        ct = getattr(value, "content_type", "") or ""
        ct_ok = ct.startswith(_ALLOWED_CT_PREFIXES)
        if not name_ok and not ct_ok:
            raise serializers.ValidationError(
                "File must be a video (mp4, mov, avi, mkv)."
                )
        # optional: size limit 50MB
        max_size = 50 * 1024 * 1024
        if getattr(value, "size", 0) > max_size:
            raise serializers.ValidationError("File size must be <= 50MB.")
        return value


class VideoVerificationPollSerializer(serializers.Serializer):
    """
    Serializer for video verification polling requests.
    """
    unique_id = serializers.CharField(
        max_length=100,
        required=True,
        help_text="Unique ID for the verification request"
    )
