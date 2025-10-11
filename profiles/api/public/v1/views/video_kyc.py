# profiles/api/public/v1/views/video_kyc.py

import hashlib
import os
import tempfile

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from profiles.api.public.v1.schema import VIDEO_KYC_SUBMIT_SCHEMA
from profiles.api.public.v1.serializers import VideoKYCSerializer
from profiles.models.kyc_video_asset import KYCVideoAsset
from profiles.tasks import submit_profile_video_auth


class VideoKYCSubmitView(generics.GenericAPIView):
    """
    Submit video authentication verification for the authenticated user's profile.
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

        # Persist a durable copy only when policy requires (approved_only or short_all)
        asset_id = None
        if getattr(settings, "KYC_VIDEO_RETENTION_MODE", "approved_only") in (
                "approved_only", "short_all"):
            asset = KYCVideoAsset.create_from_upload(
                profile=profile,
                django_file=video_file,
                storage_prefix=getattr(
                    settings, "KYC_VIDEO_STORAGE_PREFIX", "kyc_videos/"
                    ),
                created_by_attempt=None,  # بعداً در task لینک می‌شود
            )
            asset_id = asset.id
            # rewind file pointer for temp save
            try:
                video_file.seek(0)
            except Exception:
                pass

        # Save a temp file for calling provider (always)
        tmp_file_path = self._save_temp_video(video_file)

        try:
            # Submit video authentication task (async)
            task_result = submit_profile_video_auth.delay(
                profile_id=profile.id,
                national_code=profile.national_id,
                birth_date=profile.birth_date.replace("/", ""),
                selfie_video_path=tmp_file_path,
                rand_action=rand_action,
                durable_asset_id=asset_id,
            )
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
                    "success": False,
                    "error": "submission_failed",
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
                tmp_file.write(chunk)
            return tmp_file.name
