# kyc/api/public/v1/views/identity_verification.py

from rest_framework import status, mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from kyc.api.public.v1.schema import VERIFY_IDENTITY_SCHEMA
from kyc.api.public.v1.serializers.identity_verification import \
    IdentityVerificationSerializer
from kyc.services import get_identity_auth_service


class IdentityVerificationViewSet(
    mixins.CreateModelMixin, viewsets.GenericViewSet
):
    """
    POST /kyc/verify-identity/
    """
    serializer_class = IdentityVerificationSerializer

    @VERIFY_IDENTITY_SCHEMA
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        auth_service = get_identity_auth_service()
        result = auth_service.verify_identity(serializer.validated_data)

        if result.get("success"):
            return Response(
                {
                    "success": True,
                    "message": "Identity verified successfully",
                    "data": result.get("data", {})
                }, status=status.HTTP_200_OK
            )

        return Response(
            {
                "success": False,
                "message": "Identity verification failed",
                "error": result.get("error"),
                "error_code": result.get("error_code"),
                "status": result.get("status")
            }, status=status.HTTP_400_BAD_REQUEST
        )
