# apps/kyc/api/public/v1/schema/video.py

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
)

from ..serializers.video_verification import (
    VideoVerificationPollSerializer,
    VideoVerificationSubmitSerializer,
)

PROFILE_KYC_TAG = "Profile · KYC"

SUBMIT_VIDEO_SCHEMA = extend_schema(
    tags=[PROFILE_KYC_TAG],
    summary="Submit selfie video for KYC",
    request=VideoVerificationSubmitSerializer,
    responses={
        200: OpenApiResponse(
            description="Submitted successfully.",
            examples=[
                OpenApiExample(
                    "OK",
                    value={
                        "success": True,
                        "message": "Video verification submitted successfully",
                        "data": {"uniqueId": "req_123"},
                    },
                )
            ],
        ),
        400: OpenApiResponse(
            description="Validation error.",
            examples=[
                OpenApiExample(
                    "BadRequest",
                    value={
                        "success": False,
                        "message": "Validation error",
                        "errors": {
                            "selfie_video": [
                                "File must be a video (mp4, mov, avi, mkv)"
                            ]
                        },
                    },
                )
            ],
        ),
    },
)

POLL_VIDEO_SCHEMA = extend_schema(
    tags=[PROFILE_KYC_TAG],
    summary="Poll selfie video KYC result",
    request=VideoVerificationPollSerializer,
    responses={
        200: OpenApiResponse(
            description="Verification result returned successfully.",
            examples=[
                OpenApiExample(
                    "OK",
                    value={
                        "success": True,
                        "message": "Video verification result retrieved",
                        "data": {
                            "matching": 92,
                            "liveness": 88,
                            "spoofing": False,
                            "raw": {},
                        },
                    },
                )
            ],
        ),
        400: OpenApiResponse(
            description="Result not ready or error.",
            examples=[
                OpenApiExample(
                    "Pending",
                    value={
                        "success": False,
                        "message": "Could not retrieve video verification result",
                        "status": 404,
                    },
                )
            ],
        ),
    },
)
