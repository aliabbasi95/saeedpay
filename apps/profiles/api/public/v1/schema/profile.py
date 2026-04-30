# apps/profiles/api/public/v1/schema/profile.py

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

from apps.profiles.api.public.v1.serializers import ProfileSerializer

PROFILE_TAG = "Profile"

PROFILE_VIEW_SCHEMA = extend_schema(
    tags=[PROFILE_TAG],
    summary="Retrieve or update profile",
    description=(
        "Retrieve the authenticated user's profile or update allowed profile fields. "
        "Changing the phone number requires a valid OTP."
    ),
    responses={
        200: OpenApiResponse(
            response=ProfileSerializer,
            description="Profile retrieved or updated successfully.",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "phone_number": "09123456789",
                        "email": "ali@example.com",
                        "national_id": "1234567890",
                        "first_name": "Ali",
                        "last_name": "Ahmadi",
                        "birth_date": "1375/01/20",
                        "auth_stage": 1,
                        "video_auth_status": None,
                        "video_auth_last_checked_at": None,
                        "phone_national_id_match_status": None,
                        "video_task_id": None,
                    },
                )
            ],
        ),
        400: OpenApiResponse(
            description="Validation error.",
            examples=[
                OpenApiExample(
                    "PhoneUpdateNeedsOtp",
                    value={"otp_code": "کد تایید الزامی است هنگام تغییر شماره تلفن."},
                ),
                OpenApiExample(
                    "MixedUpdate",
                    value={
                        "non_field_errors": (
                            "نمی‌توانید همزمان شماره تلفن و سایر فیلدهای پروفایل را "
                            "به‌روزرسانی کنید. لطفاً یکی را انتخاب کنید."
                        )
                    },
                ),
            ],
        ),
    },
)
