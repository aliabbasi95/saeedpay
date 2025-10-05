# profiles/api/public/v1/serializers/profile.py

import re

from django.db import transaction
from rest_framework import serializers

from auth_api.api.public.v1.serializers.mixins import OTPValidationMixin
from profiles.models.profile import Profile
from profiles.tasks import verify_identity_phone_national_id
from profiles.utils.choices import AuthenticationStage


class ProfileSerializer(serializers.ModelSerializer, OTPValidationMixin):
    phone_number = serializers.CharField(
        max_length=11, min_length=11, required=False
    )
    email = serializers.EmailField(required=False, allow_blank=True)
    national_id = serializers.CharField(
        max_length=10, min_length=10, required=False
    )
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    birth_date = serializers.CharField(required=False)

    otp_code = serializers.CharField(write_only=True, required=False)

    kyc_status = serializers.CharField(read_only=True, allow_null=True)
    auth_stage = serializers.IntegerField(read_only=True)
    kyc_last_checked_at = serializers.DateTimeField(
        read_only=True, allow_null=True
    )
    phone_national_id_match_status = serializers.CharField(
        read_only=True, allow_null=True
    )
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
        if value and not re.match(r"^09\d{9}$", value):
            raise serializers.ValidationError(
                "شماره تلفن معتبر نیست. باید با 09 شروع شده و 11 رقم باشد."
            )
        return value

    def validate_national_id(self, value):
        return value

    def validate(self, data):
        phone_number = data.get("phone_number")
        otp_code = data.get("otp_code")

        basic_profile_fields = {
            "first_name",
            "last_name",
            "national_id",
            "birth_date",
            "email"
        }
        provided_basic_fields = basic_profile_fields.intersection(data.keys())
        phone_update_attempted = phone_number is not None

        if phone_update_attempted and provided_basic_fields:
            raise serializers.ValidationError(
                {
                    "non_field_errors": (
                        "نمی‌توانید همزمان شماره تلفن و سایر فیلدهای پروفایل را به‌روزرسانی کنید. لطفاً یکی را انتخاب کنید.")
                }
            )

        if not phone_update_attempted and not provided_basic_fields:
            raise serializers.ValidationError(
                {
                    "non_field_errors": (
                        "لطفاً حداقل یک فیلد مجاز ارسال کنید یا phone_number با otp_code.")
                }
            )

        if phone_update_attempted:
            if not otp_code:
                raise serializers.ValidationError(
                    {"otp_code": "کد تایید الزامی است هنگام تغییر شماره تلفن."}
                )
            self.validate_phone_otp(phone_number, otp_code)

        return data

    def update(self, instance, validated_data):
        # بلاک تغییرات هنگام پردازش‌ها
        if instance.kyc_status == "processing":
            raise serializers.ValidationError(
                {"non_field_errors": ["در حال پردازش KYC هستید."]}
            )
        if instance.phone_national_id_match_status == "processing":
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "در حال بررسی مالکیت شماره/کدملی هستید."]
                }
            )

        validated_data.pop("otp_code", None)

        national_id_updated = "national_id" in validated_data and \
                              validated_data[
                                  "national_id"] != instance.national_id
        phone_updated = "phone_number" in validated_data and validated_data[
            "phone_number"] != instance.phone_number

        if national_id_updated and instance.auth_stage in [
            AuthenticationStage.IDENTITY_VERIFIED,
            AuthenticationStage.VIDEO_VERIFIED,
        ]:
            raise serializers.ValidationError(
                {"national_id": "بعد از احراز هویت، تغییر کدملی مجاز نیست."}
            )

        if phone_updated and instance.auth_stage in [
            AuthenticationStage.IDENTITY_VERIFIED,
            AuthenticationStage.VIDEO_VERIFIED,
        ]:
            raise serializers.ValidationError(
                {
                    "phone_number": "بعد از احراز هویت، تغییر شماره تلفن مجاز نیست."
                }
            )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if phone_updated or national_id_updated:
            instance.auth_stage = AuthenticationStage.SIGNUP
            instance.kyc_status = None
            instance.video_task_id = None
            instance.kyc_last_checked_at = None
            instance.phone_national_id_match_status = None
            instance.identity_verified_at = None
            instance.video_submitted_at = None
            instance.video_verified_at = None

        instance.save()

        if national_id_updated:
            transaction.on_commit(
                lambda: verify_identity_phone_national_id.delay(instance.id)
            )

        return instance
