# kyc/api/public/v1/serializers/video_verification.py

from rest_framework import serializers


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
        """Validate national ID format."""
        if not value or len(value) != 10 or not value.isdigit():
            raise serializers.ValidationError("Invalid national ID format. Must be 10 digits.")
        return value

    def validate_birth_date(self, value):
        """Validate birth date format."""
        if not value or not value.replace("/", "").isdigit() or len(value.replace("/", "")) != 8:
            raise serializers.ValidationError("Invalid birth date format. Must be YYYY/MM/DD.")
        return value.replace("/", "")

    def validate_selfie_video(self, value):
        """Validate selfie video file."""
        if value:
            # Check file extension
            allowed_extensions = [".mp4", ".mov", ".avi", ".mkv"]
            if not any(value.name.lower().endswith(ext) for ext in allowed_extensions):
                raise serializers.ValidationError(
                    "File must be a video (mp4, mov, avi, mkv)"
                )
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
