# profiles/api/public/v1/serializers/profile.py

from django.db import transaction
from rest_framework import serializers

from profiles.models.profile import Profile
from profiles.utils.choices import AuthenticationStage
from auth_api.models import PhoneOTP
from auth_api.api.public.v1.serializers.mixins import OTPValidationMixin
from profiles.tasks import mock_identity_verification
import re


class ProfileSerializer(serializers.ModelSerializer, OTPValidationMixin):
    phone_number = serializers.CharField(max_length=11, min_length=11, required=False)
    email = serializers.EmailField(required=False, allow_blank=True)
    national_id = serializers.CharField(max_length=10, min_length=10, required=False)
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    birth_date = serializers.CharField(required=False)

    # OTP verification fields
    otp_code = serializers.CharField(write_only=True, required=False)

    kyc_status = serializers.CharField(read_only=True, allow_null=True)
    auth_stage = serializers.IntegerField(read_only=True)
    kyc_last_checked_at = serializers.DateTimeField(read_only=True, allow_null=True)
    phone_national_id_match_status = serializers.CharField(read_only=True, allow_null=True)
    video_task_id = serializers.CharField(read_only=True)

    class Meta:
        model = Profile
        fields = [
            "phone_number",
            "email",
            "national_id",
            "first_name",
            "last_name",
            "birth_date",
            "auth_stage",
            "kyc_status",
            "kyc_last_checked_at",
            "phone_national_id_match_status",
            "video_task_id",
            "otp_code",
        ]

    def validate_phone_number(self, value):
        """Validate phone number format."""

        if value and not re.match(r"^09\d{9}$", value):
            raise serializers.ValidationError(
                "شماره تلفن معتبر نیست. باید با 09 شروع شده و 11 رقم باشد."
            )
        return value

    def validate_national_id(self, value):
        """Validate national ID format."""
        if value:
            # Add national ID validation logic here if needed
            pass
        return value

    def validate(self, data):
        """
        Validate that user sends either:
        1. Basic profile fields (first_name, last_name, national_id, birth_date, email)
        2. Phone number update with OTP code
        
        These two groups are mutually exclusive.
        """
        phone_number = data.get("phone_number")
        otp_code = data.get("otp_code")
        
        # Define basic profile fields
        basic_profile_fields = {"first_name", "last_name", "national_id", "birth_date", "email"}
        provided_basic_fields = basic_profile_fields.intersection(data.keys())
        
        # Check if phone number update is being attempted
        phone_update_attempted = phone_number is not None
        
        # Enforce mutual exclusivity
        if phone_update_attempted and provided_basic_fields:
            raise serializers.ValidationError(
                {
                    "non_field_errors": (
                        "نمی‌توانید همزمان شماره تلفن و سایر فیلدهای پروفایل را به‌روزرسانی کنید. "
                        "لطفاً یکی از این دو عملیات را انتخاب کنید."
                    )
                }
            )
        
        # If no valid fields provided
        if not phone_update_attempted and not provided_basic_fields:
            raise serializers.ValidationError(
                {
                    "non_field_errors": (
                        "لطفاً حداقل یک فیلد برای به‌روزرسانی ارسال کنید. "
                        "فیلدهای مجاز: first_name, last_name, national_id, birth_date, email یا phone_number با otp_code"
                    )
                }
            )
        
        # Validate phone number update
        if phone_update_attempted:
            # OTP code is required for phone number updates
            if not otp_code:
                raise serializers.ValidationError(
                    {"otp_code": "کد تایید الزامی است هنگام تغییر شماره تلفن."}
                )
            
            # Validate OTP code
            self.validate_phone_otp(phone_number, otp_code)

        return data

    def update(self, instance, validated_data):
        """Update profile and reset auth_stage when phone_number or national_id changes."""
        # Prevent updates when kyc_status is PROCESSING
        if instance.kyc_status == "processing":
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "نمی‌توانید پروفایل را به‌روزرسانی کنید وقتی که "
                        "احراز هویت در حال انجام است."
                    ]
                }
            )
        
        # Prevent updates when phone_national_id_match_status is PROCESSING
        if instance.phone_national_id_match_status == "processing":
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "نمی‌توانید پروفایل را به‌روزرسانی کنید وقتی که "
                        "احراز هویت شماره تلفن و کد ملی در حال انجام است."
                    ]
                }
            )
        
        # Remove OTP code from validated data as it's not a model field
        otp_code = validated_data.pop("otp_code", None)

        # Check if national_id is being updated
        national_id_updated = (
            "national_id" in validated_data
            and validated_data["national_id"] != instance.national_id
        )

        # Prevent national_id changes when auth_stage is IDENTITY_VERIFIED or VIDEO_VERIFIED
        if national_id_updated and instance.auth_stage in [
            AuthenticationStage.IDENTITY_VERIFIED,
            AuthenticationStage.VIDEO_VERIFIED,
        ]:
            raise serializers.ValidationError(
                {
                    "national_id": (
                        "نمی‌توانید کد ملی را تغییر دهید وقتی که مرحله "
                        "احراز هویت شناسایی یا ویدیویی را پشت سر گذاشته‌اید."
                    )
                }
            )

        # Check if phone_number is being updated
        phone_updated = (
            "phone_number" in validated_data
            and validated_data["phone_number"] != instance.phone_number
        )

        # CRITICAL: Prevent phone_number changes after IDENTITY_VERIFIED or VIDEO_VERIFIED
        if phone_updated and instance.auth_stage in [
            AuthenticationStage.IDENTITY_VERIFIED,
            AuthenticationStage.VIDEO_VERIFIED,
        ]:
            raise serializers.ValidationError(
                {
                    "phone_number": (
                        "نمی‌توانید شماره تلفن را تغییر دهید وقتی که مرحله "
                        "احراز هویت شناسایی یا ویدیویی را پشت سر گذاشته‌اید. "
                        "برای تغییر شماره تلفن، با پشتیبانی تماس بگیرید."
                    )
                }
            )

        # Update the instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # If phone_number or national_id was updated, reset ALL KYC-related fields
        if phone_updated or national_id_updated:
            instance.auth_stage = AuthenticationStage.SIGNUP
            instance.kyc_status = None
            instance.video_task_id = None
            instance.kyc_last_checked_at = None
            instance.phone_national_id_match_status = None
            instance.identity_verified_at = None
            instance.video_submitted_at = None
            instance.video_verified_at = None

        # Save first to ensure changes are persisted
        instance.save()

        # If national_id was updated, trigger mock identity verification task AFTER save
        if national_id_updated:
            # Use transaction.on_commit to ensure task sees the saved data
            transaction.on_commit(
                lambda: mock_identity_verification.delay(instance.id)
            )

        return instance
