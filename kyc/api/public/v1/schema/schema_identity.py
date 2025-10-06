# kyc/api/public/v1/schema/schema_identity.py

from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
    OpenApiExample,
)

from ..serializers.identity_verification import IdentityVerificationSerializer

VERIFY_IDENTITY_SCHEMA = extend_schema(
    tags=["KYC"],
    summary="Verify identity (national_id/phone)",
    request=IdentityVerificationSerializer,
    responses={
        200: OpenApiResponse(
            description="Verification succeeded",
            examples=[OpenApiExample(
                "OK", value={
                    "success": True,
                    "message": "Identity verified successfully",
                    "data": {"uniqueId": "abc123", "matched": True}
                }
            )],
        ),
        400: OpenApiResponse(
            description="Validation error",
            examples=[OpenApiExample(
                "BadRequest", value={
                    "success": False,
                    "message": "Validation error",
                    "errors": {"national_id": ["Invalid national ID format"]}
                }
            )],
        ),
    },
)
