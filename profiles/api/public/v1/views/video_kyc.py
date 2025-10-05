# profiles/api/public/v1/views/video_kyc.py

import os
import tempfile
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from profiles.api.public.v1.serializers import VideoKYCSerializer
from profiles.tasks import submit_profile_video_kyc


class VideoKYCSubmitView(APIView):
    """
    Submit video KYC verification for the authenticated user's profile.
    All validation is handled in the serializer.
    """
    serializer_class = VideoKYCSerializer

    @extend_schema(
        tags=["Profile"],
        summary="ارسال ویدیو برای احراز هویت",
        description="ارسال ویدیو سلفی برای احراز هویت ویدیویی کاربر",
        request=VideoKYCSerializer,
        responses={
            200: {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "message": {"type": "string"},
                    "task_id": {"type": "string"},
                },
            },
            400: {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "errors": {"type": "object"},
                },
            },
        },
    )
    def post(self, request):
        # Validate request data and profile state
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        # Extract validated data
        profile = serializer.validated_data['_profile']
        video_file = serializer.validated_data['selfieVideo']
        rand_action = serializer.validated_data['randAction']

        # Save video to temporary file
        tmp_file_path = self._save_temp_video(video_file)

        try:
            # Submit video KYC task
            task_result = submit_profile_video_kyc.delay(
                profile_id=profile.id,
                national_code=profile.national_id,
                birth_date=profile.birth_date.replace("/", ""),
                selfie_video_path=tmp_file_path,
                rand_action=rand_action,
            )

            return Response(
                {
                    "success": True,
                    "message": "درخواست احراز هویت ویدیویی با موفقیت ثبت شد.",
                    "task_id": task_result.id,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            # Clean up temporary file on error
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

            return Response(
                {"success": False, "error": "submission_failed", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _save_temp_video(self, video_file) -> str:
        """Save uploaded video to a temporary file and return its path."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(video_file.name)[1]
        ) as tmp_file:
            for chunk in video_file.chunks():
                tmp_file.write(chunk)
            return tmp_file.name
