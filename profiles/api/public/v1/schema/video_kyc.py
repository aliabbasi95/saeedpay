# profiles/api/public/v1/schema/video_kyc.py

from drf_spectacular.utils import (
    extend_schema, OpenApiResponse,
    OpenApiExample,
)

from profiles.api.public.v1.serializers.video_kyc import VideoKYCSerializer

VIDEO_KYC_SUBMIT_SCHEMA = extend_schema(
    tags=["Profile"],
    summary="ارسال ویدیو برای احراز هویت",
    description=(
        "آپلود ویدیو سلفی برای احراز هویت ویدیویی کاربر. این عملیات غیرهمزمان است "
        "و شناسه‌ی تسک Celery برمی‌گرداند."
    ),
    request=VideoKYCSerializer,  # multipart/form-data
    responses={
        202: OpenApiResponse(
            description="درخواست ثبت شد (غیرهمزمان)",
            examples=[
                OpenApiExample(
                    "Accepted",
                    value={
                        "success": True,
                        "message": "درخواست احراز هویت ویدیویی با موفقیت ثبت شد.",
                        "task_id": "1d0a3b9a-3e7a-4a1e-9a7c-3fb3a3c1f0a2",
                    },
                )
            ],
        ),
        400: OpenApiResponse(
            description="خطای اعتبارسنجی",
            examples=[
                OpenApiExample(
                    "BadRequest",
                    value={
                        "success": False,
                        "errors": {
                            "selfieVideo": [
                                "فایل باید یک ویدیو باشد (mp4, mov, avi, mkv)"]
                        },
                    },
                )
            ],
        ),
        500: OpenApiResponse(
            description="خطای داخلی",
            examples=[
                OpenApiExample(
                    "ServerError",
                    value={
                        "success": False,
                        "error": "submission_failed",
                        "message": "Temporary storage error",
                    },
                )
            ],
        ),
    },
)
