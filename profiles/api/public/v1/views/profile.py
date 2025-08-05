# profiles/api/public/v1/views/profile.py

from drf_spectacular.utils import extend_schema
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
        profile, _ = Profile.objects.get_or_create(user=request.user)
        serializer = self.serializer_class(
            profile, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
