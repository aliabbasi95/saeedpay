# apps/profiles/api/public/v1/views/profile.py

from rest_framework import generics

from apps.profiles.api.public.v1.schema import PROFILE_VIEW_SCHEMA
from apps.profiles.api.public.v1.serializers import ProfileSerializer
from apps.profiles.models.profile import Profile


@PROFILE_VIEW_SCHEMA
class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer

    def get_object(self):
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        return profile
