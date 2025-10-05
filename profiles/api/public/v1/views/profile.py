# profiles/api/public/v1/views/profile.py

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from profiles.api.public.v1.serializers import ProfileSerializer
from profiles.models.profile import Profile


@extend_schema(
    tags=["Profile"],
    summary="دریافت اطلاعات پروفایل",
    description="بررسی یا ایجاد و بازگردانی اطلاعات پروفایل کاربر لاگین‌شده"
)
class ProfileView(APIView):
    serializer_class = ProfileSerializer

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        data = self.serializer_class(profile).data
        return Response(data)

    def post(self, request):
        """
        Update profile with either:
        1. Basic profile fields (first_name, last_name, national_id, birth_date, email)
        2. Phone number with OTP verification
        
        These two update types are mutually exclusive.
        """
        profile, _ = Profile.objects.get_or_create(user=request.user)
        serializer = self.serializer_class(
            profile, data=request.data, partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(
            {
                "success": False,
                "errors": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
