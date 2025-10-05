# profiles/api/public/v1/serializers/video_kyc.py

from rest_framework import serializers


class VideoKYCSerializer(serializers.Serializer):
    selfieVideo = serializers.FileField(required=True)
    randAction = serializers.CharField(required=True)

    def validate_selfieVideo(self, value):
        # Validate that the file is a video
        if value:
            # Check file extension
            allowed_extensions = [".mp4", ".mov", ".avi", ".mkv"]
            if not any(value.name.lower().endswith(ext) for ext in allowed_extensions):
                raise serializers.ValidationError(
                    "فایل باید یک ویدیو باشد (mp4, mov, avi, mkv)"
                )
        return value
