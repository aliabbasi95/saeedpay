# profiles/api/public/v1/views/video_kyc.py

import os
import tempfile
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from profiles.api.public.v1.serializers import VideoKYCSerializer
from profiles.models.profile import Profile
from profiles.tasks import submit_profile_video_kyc


class VideoKYCSubmitView(APIView):
    """
    Submit video KYC verification for the authenticated user's profile.
    This endpoint handles the video file upload and triggers the KYC verification process.
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
                    "error": {"type": "string"},
                    "message": {"type": "string"},
                },
            },
        },
    )
    def post(self, request):
        try:
            profile = Profile.objects.get(user=request.user)
        except Profile.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "profile_not_found",
                    "message": "پروفایل کاربری یافت نشد.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if profile has required fields for video KYC
        if not profile.national_id:
            return Response(
                {
                    "success": False,
                    "error": "missing_national_id",
                    "message": "کد ملی در پروفایل شما ثبت نشده است.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not profile.birth_date:
            return Response(
                {
                    "success": False,
                    "error": "missing_birth_date",
                    "message": "تاریخ تولد در پروفایل شما ثبت نشده است.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if user is eligible to submit video KYC
        # Only users with auth_stage of IDENTITY_VERIFIED can submit
        if profile.auth_stage != Profile.AuthenticationStage.IDENTITY_VERIFIED:
            return Response(
                {
                    "success": False,
                    "error": "invalid_auth_stage",
                    "message": "کاربر باید در مرحله احراز هویت شناسایی قرار داشته باشد.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check KYC status - prevent submission if already PROCESSING or ACCEPTED
        if profile.kyc_status == profile.KYCStatus.PROCESSING:
            return Response(
                {
                    "success": False,
                    "error": "kyc_in_progress",
                    "message": "درخواست احراز هویت ویدیویی شما در حال پردازش است.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if profile.kyc_status == profile.KYCStatus.ACCEPTED:
            return Response(
                {
                    "success": False,
                    "error": "already_verified",
                    "message": "احراز هویت شما قبلاً تایید شده است.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Save video file temporarily
        video_file = request.FILES.get("selfieVideo")
        if not video_file:
            return Response(
                {
                    "success": False,
                    "error": "missing_video_file",
                    "message": "فایل ویدیو سلفی الزامی است.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create a temporary file to store the video
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(video_file.name)[1]
        ) as tmp_file:
            for chunk in video_file.chunks():
                tmp_file.write(chunk)
            tmp_file_path = tmp_file.name

        try:
            # Submit video KYC task
            task_result = submit_profile_video_kyc.delay(
                profile_id=profile.id,
                national_code=profile.national_id,
                birth_date=profile.birth_date.replace(
                    "/", ""
                ),  # Remove slashes for API format
                selfie_video_path=tmp_file_path,
                rand_action=serializer.validated_data["randAction"],
            )

            # Note: Celery task is responsible for cleaning up the temp file
            # Do not delete it here as the task needs it
            return Response(
                {
                    "success": True,
                    "message": "درخواست احراز هویت ویدیویی با موفقیت ثبت شد.",
                    "task_id": task_result.id,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            # Clean up temporary file in case of error
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

            return Response(
                {"success": False, "error": "submission_failed", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
