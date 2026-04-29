# profiles/api/public/v1/schema/video_kyc.py

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

from profiles.api.public.v1.serializers.video_kyc import VideoKYCSerializer

PROFILE_KYC_TAG = "Profile · KYC"

VIDEO_KYC_SUBMIT_SCHEMA = extend_schema(
    tags=[PROFILE_KYC_TAG],
    summary="Submit video KYC",
    description=(
        "Upload a selfie video for video-based identity verification. "
        "This operation is asynchronous and returns a Celery task ID."
    ),
    request=VideoKYCSerializer,
    responses={
        202: OpenApiResponse(
            description="Video KYC request accepted.",
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
            description="Validation error.",
            examples=[
                OpenApiExample(
                    "InvalidVideo",
                    value={
                        "success": False,
                        "errors": {
                            "selfieVideo": [
                                "فایل باید یک ویدیو باشد (mp4, mov, avi, mkv)"
                            ]
                        },
                    },
                )
            ],
        ),
        500: OpenApiResponse(
            description="Internal server error.",
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
