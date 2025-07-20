# profiles/api/public/v1/serializers/profile.py

from rest_framework import serializers

from profiles.models.profile import Profile


class ProfileSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(read_only=True)

    class Meta:
        model = Profile
        fields = [
            "phone_number",
            "email",
            "national_id",
            "first_name",
            "last_name",
            "birth_date"
        ]
