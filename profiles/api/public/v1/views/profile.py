# profiles/api/public/v1/views/profile.py

from drf_spectacular.utils import extend_schema
from rest_framework import generics

from profiles.api.public.v1.serializers import ProfileSerializer
from profiles.models.profile import Profile


@extend_schema(
    tags=["Profile"],
    summary="دریافت/ویرایش پروفایل",
    description="دریافت پروفایل کاربر لاگین‌شده یا بروزرسانی فیلدهای مجاز. بروزرسانی شماره تلفن نیازمند OTP است.",
)
class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer

    def get_object(self):
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        return profile
