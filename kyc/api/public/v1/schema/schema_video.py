# kyc/api/public/v1/schema/schema_video.py

from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
    OpenApiExample,
)

from ..serializers.video_verification import (
    VideoVerificationSubmitSerializer,
    VideoVerificationPollSerializer,
)

SUBMIT_VIDEO_SCHEMA = extend_schema(
    tags=["KYC"],
    summary="Submit selfie video for KYC",
    request=VideoVerificationSubmitSerializer,
    responses={
        200: OpenApiResponse(
            description="Submitted",
            examples=[OpenApiExample(
                "OK", value={
                    "success": True,
                    "message": "Video verification submitted successfully",
                    "data": {"uniqueId": "req_123"}
                }
            )],
        ),
        400: OpenApiResponse(
            description="Validation error",
            examples=[OpenApiExample(
                "BadRequest", value={
                    "success": False,
                    "message": "Validation error",
                    "errors": {
                        "selfie_video": [
                            "File must be a video (mp4, mov, avi, mkv)"]
                    }
                }
            )],
        ),
    },
)

POLL_VIDEO_SCHEMA = extend_schema(
    tags=["KYC"],
    summary="Poll selfie video KYC result",
    request=VideoVerificationPollSerializer,
    responses={
        200: OpenApiResponse(
            description="Result",
            examples=[OpenApiExample(
                "OK", value={
                    "success": True,
                    "message": "Video verification result retrieved",
                    "data": {
                        "matching": 92, "liveness": 88, "spoofing": False,
                        "raw": {}
                    }
                }
            )],
        ),
        400: OpenApiResponse(
            description="Not ready / error",
            examples=[OpenApiExample(
                "Pending", value={
                    "success": False,
                    "message": "Could not retrieve video verification result",
                    "status": 404
                }
            )],
        ),
    },
)
