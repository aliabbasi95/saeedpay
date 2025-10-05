# profiles/api/public/v1/views/video_kyc.py

import os
import tempfile

from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from profiles.api.public.v1.schema import VIDEO_KYC_SUBMIT_SCHEMA
from profiles.api.public.v1.serializers import VideoKYCSerializer
from profiles.tasks import submit_profile_video_kyc


class VideoKYCSubmitView(generics.GenericAPIView):
    """
    Submit video KYC verification for the authenticated user's profile.
    Validation is handled by the serializer.
    """
    serializer_class = VideoKYCSerializer
    permission_classes = [IsAuthenticated]

    @VIDEO_KYC_SUBMIT_SCHEMA
    def post(self, request, *args, **kwargs):
        # Validate request data and profile state
        serializer = self.get_serializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        # Extract validated data
        profile = serializer.validated_data['_profile']
        video_file = serializer.validated_data['selfieVideo']
        rand_action = serializer.validated_data['randAction']

        # Save video to temporary file
        tmp_file_path = self._save_temp_video(video_file)

        try:
            # Submit video KYC task (async)
            task_result = submit_profile_video_kyc.delay(
                profile_id=profile.id,
                national_code=profile.national_id,
                birth_date=profile.birth_date.replace("/", ""),
                selfie_video_path=tmp_file_path,
                rand_action=rand_action,
            )

            # 202 Accepted (async processing)
            return Response(
                {
                    "success": True,
                    "message": "درخواست احراز هویت ویدیویی با موفقیت ثبت شد.",
                    "task_id": task_result.id,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception as e:
            # Clean up temporary file on error
            if os.path.exists(tmp_file_path):
                try:
                    os.unlink(tmp_file_path)
                except Exception:
                    pass

            return Response(
                {
                    "success": False, "error": "submission_failed",
                    "message": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _save_temp_video(self, video_file) -> str:
        """Save uploaded video to a temporary file and return its absolute path."""
        suffix = os.path.splitext(video_file.name)[1] or ".mp4"
        with tempfile.NamedTemporaryFile(
                delete=False, suffix=suffix
        ) as tmp_file:
            for chunk in video_file.chunks():
                tmp_file._
