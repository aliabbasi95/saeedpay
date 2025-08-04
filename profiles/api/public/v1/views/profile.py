# profiles/api/public/v1/views/profile.py

from drf_spectacular.utils import extend_schema

from lib.cas_auth.views import PublicAPIView
from profiles.api.public.v1.serializers import ProfileSerializer
from profiles.models.profile import Profile


@extend_schema(
    tags=["Profile"],
    summary="دریافت اطلاعات پروفایل",
    description="بررسی یا ایجاد و بازگردانی اطلاعات پروفایل کاربر لاگین‌شده"
)
class ProfileView(PublicAPIView):
    serializer_class = ProfileSerializer

    def get(self, request):
        profile, created = Profile.objects.get_or_create(user=request.user)
        self.response_data = self.serializer_class(profile).data
        self.response_status = 200
        return self.response

    def post(self, request):
        profile, created = Profile.objects.get_or_create(user=request.user)
        serializer = self.serializer_class(
            profile, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        self.response_data = serializer.data
        self.response_status = 200
        return self.response
