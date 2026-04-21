# kyc/api/public/v1/schema/identity.py

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
)

from ..serializers.identity_verification import IdentityVerificationSerializer

PROFILE_KYC_TAG = "Profile · KYC"

VERIFY_IDENTITY_SCHEMA = extend_schema(
    tags=[PROFILE_KYC_TAG],
    summary="Verify identity by national ID and phone number",
    request=IdentityVerificationSerializer,
    responses={
        200: OpenApiResponse(
            description="Verification succeeded.",
            examples=[
                OpenApiExample(
                    "OK",
                    value={
                        "success": True,
                        "message": "Identity verified successfully",
                        "data": {"uniqueId": "abc123", "matched": True},
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
                        "errors": {"national_id": ["Invalid national ID format"]},
                    },
                )
            ],
        ),
    },
)
