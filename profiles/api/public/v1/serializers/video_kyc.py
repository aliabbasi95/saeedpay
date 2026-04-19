# profiles/api/public/v1/serializers/video_kyc.py

from rest_framework import serializers

from profiles.models.profile import Profile
from profiles.utils.choices import KYCStatus


class VideoKYCSerializer(serializers.Serializer):
    selfieVideo = serializers.FileField(required=True)
    randAction = serializers.CharField(required=True, max_length=1000)

    def validate_selfieVideo(self, value):
        """Validate video file format and size."""
        if not value:
            raise serializers.ValidationError("فایل ویدیو الزامی است.")

        max_size = 50 * 1024 * 1024  # 50MB
        if value.size > max_size:
            raise serializers.ValidationError(
                "حجم فایل نباید بیشتر از ۵۰ مگابایت باشد."
            )

        return value

    def validate(self, data):
        """Validate profile state and eligibility for video KYC submission."""
        request = self.context.get("request")
        if not request or not request.user:
            raise serializers.ValidationError(
                {"non_field_errors": ["کاربر احراز هویت نشده است."]}
            )

        try:
            profile = Profile.objects.get(user=request.user)
        except Profile.DoesNotExist as exc:
            raise serializers.ValidationError(
                {"non_field_errors": ["پروفایل کاربری یافت نشد."]}
            ) from exc

        if not profile.national_id:
            raise serializers.ValidationError(
                {"non_field_errors": ["کد ملی در پروفایل شما ثبت نشده است."]}
            )

        if not profile.birth_date:
            raise serializers.ValidationError(
                {"non_field_errors": ["تاریخ تولد در پروفایل شما ثبت نشده است."]}
            )

        if not profile.can_submit_video_auth():
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "کاربر باید در مرحله احراز هویت شناسایی قرار داشته باشد."
                    ]
                }
            )

        if profile.is_video_auth_in_progress():
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "درخواست احراز هویت ویدیویی شما در حال پردازش است."
                    ]
                }
            )

        if profile.video_auth_status == KYCStatus.ACCEPTED:
            raise serializers.ValidationError(
                {"non_field_errors": ["احراز هویت شما قبلاً تایید شده است."]}
            )

        data["_profile"] = profile
        return data
