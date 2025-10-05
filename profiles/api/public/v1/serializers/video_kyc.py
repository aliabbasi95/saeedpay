# profiles/api/public/v1/serializers/video_kyc.py

from rest_framework import serializers
from profiles.models.profile import Profile
from profiles.utils.choices import KYCStatus


class VideoKYCSerializer(serializers.Serializer):
    selfieVideo = serializers.FileField(required=True)
    randAction = serializers.CharField(required=True, max_length=100)

    def validate_selfieVideo(self, value):
        """Validate video file format and size."""
        if not value:
            raise serializers.ValidationError("فایل ویدیو الزامی است.")
        
        # Check file extension
        allowed_extensions = [".mp4", ".mov", ".avi", ".mkv"]
        if not any(value.name.lower().endswith(ext) for ext in allowed_extensions):
            raise serializers.ValidationError(
                "فایل باید یک ویدیو باشد (mp4, mov, avi, mkv)"
            )
        
        # Check file size (max 50MB)
        max_size = 50 * 1024 * 1024  # 50MB
        if value.size > max_size:
            raise serializers.ValidationError(
                "حجم فایل نباید بیشتر از ۵۰ مگابایت باشد."
            )
        
        return value

    def validate(self, data):
        """Validate profile state and eligibility for video KYC submission."""
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError(
                {"non_field_errors": ["کاربر احراز هویت نشده است."]}
            )

        # Get or validate profile exists
        try:
            profile = Profile.objects.get(user=request.user)
        except Profile.DoesNotExist:
            raise serializers.ValidationError(
                {"non_field_errors": ["پروفایل کاربری یافت نشد."]}
            )

        # Check required profile fields
        if not profile.national_id:
            raise serializers.ValidationError(
                {"non_field_errors": ["کد ملی در پروفایل شما ثبت نشده است."]}
            )

        if not profile.birth_date:
            raise serializers.ValidationError(
                {"non_field_errors": ["تاریخ تولد در پروفایل شما ثبت نشده است."]}
            )

        # Validate auth stage
        if not profile.can_submit_video_kyc():
            raise serializers.ValidationError(
                {"non_field_errors": ["کاربر باید در مرحله احراز هویت شناسایی قرار داشته باشد."]}
            )

        # Check if already in progress
        if profile.is_video_kyc_in_progress():
            raise serializers.ValidationError(
                {"non_field_errors": ["درخواست احراز هویت ویدیویی شما در حال پردازش است."]}
            )

        # Check if already accepted
        if profile.kyc_status == KYCStatus.ACCEPTED:
            raise serializers.ValidationError(
                {"non_field_errors": ["احراز هویت شما قبلاً تایید شده است."]}
            )

        # Store profile in validated data for use in view
        data['_profile'] = profile
        return data
