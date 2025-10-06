# kyc/api/public/v1/views/video_verification.py

import os
import tempfile

from kyc.api.public.v1.schema import (
    SUBMIT_VIDEO_SCHEMA,
    POLL_VIDEO_SCHEMA,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from kyc.api.public.v1.permissions import IsIdentityVerified
from kyc.api.public.v1.serializers.video_verification import (
    VideoVerificationSubmitSerializer, VideoVerificationPollSerializer,
)
from kyc.services import get_identity_auth_service


class VideoVerificationViewSet(viewsets.GenericViewSet):
    """
    Handles:
      - POST /kyc/video/submit/   (create)
      - POST /kyc/video/poll/     (custom action)
    """

    @SUBMIT_VIDEO_SCHEMA
    @action(
        detail=False, methods=["post"],
        permission_classes=[IsAuthenticated, IsIdentityVerified],
        url_path="submit"
    )
    def submit(self, request):
        serializer = VideoVerificationSubmitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "message": "Validation error",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST
            )

        auth_service = get_identity_auth_service()

        video_file = request.FILES.get("selfie_video")
        if not video_file:
            return Response(
                {
                    "success": False,
                    "message": "Selfie video file is required"
                }, status=status.HTTP_400_BAD_REQUEST
            )

        tmp_file_path = None
        try:
            # safe temp-save
            suffix = os.path.splitext(getattr(video_file, "name", "upload"))[1]
            with tempfile.NamedTemporaryFile(
                    delete=False, suffix=suffix
            ) as tmp:
                for chunk in video_file.chunks():
                    tmp.write(chunk)
                tmp_file_path = tmp.name

            result = auth_service.verify_idcard_video(
                national_code=serializer.validated_data["national_id"],
                birth_date=serializer.validated_data["birth_date"],
                # already normalized YYYYMMDD
                selfie_video_path=tmp_file_path,
                rand_action=serializer.validated_data["rand_action"],
                matching_thr=serializer.validated_data.get("matching_thr"),
                liveness_thr=serializer.validated_data.get("liveness_thr"),
            )

            if result.get("success"):
                return Response(
                    {
                        "success": True,
                        "message": "Video verification submitted successfully",
                        "data": result.get("data", {})
                    }, status=status.HTTP_200_OK
                )

            return Response(
                {
                    "success": False,
                    "message": "Video verification submission failed",
                    "error": result.get("error"),
                    "status": result.get("status")
                }, status=status.HTTP_400_BAD_REQUEST
            )

        finally:
            if tmp_file_path and os.path.exists(tmp_file_path):
                try:
                    os.unlink(tmp_file_path)
                except Exception:
                    pass

    @POLL_VIDEO_SCHEMA
    @action(
        detail=False, methods=["post"], permission_classes=[IsAuthenticated],
        url_path="poll"
    )
    def poll(self, request):
        serializer = VideoVerificationPollSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "message": "Validation error",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST
            )

        auth_service = get_identity_auth_service()
        result = auth_service.get_video_verification_result(
            serializer.validated_data["unique_id"]
        )

        if result.get("success"):
            return Response(
                {
                    "success": True,
                    "message": "Video verification result retrieved",
                    "data": {
                        "matching": result.get("matching"),
                        "liveness": result.get("liveness"),
                        "spoofing": result.get("spoofing"),
                        "raw": result.get("raw"),
                    }
                }, status=status.HTTP_200_OK
            )

        return Response(
            {
                "success": False,
                "message": "Could not retrieve video verification result",
                "error": result.get("error"),
                "status": result.get("status")
            }, status=status.HTTP_400_BAD_REQUEST
        )
