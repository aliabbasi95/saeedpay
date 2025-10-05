# kyc/api/public/v1/permissions.py

from typing import Any

from rest_framework.permissions import BasePermission

from profiles.models import Profile
from profiles.utils.choices import AuthenticationStage


class IsIdentityVerified(BasePermission):
    """Allow only users with profile at IDENTITY_VERIFIED stage."""

    def has_permission(self, request: Any, view: Any) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        profile = getattr(user, "profile", None)
        if not isinstance(profile, Profile):
            return False
        return profile.auth_stage == AuthenticationStage.IDENTITY_VERIFIED


class IsVideoVerified(BasePermission):
    """Allow only users with profile at VIDEO_VERIFIED stage."""

    def has_permission(self, request: Any, view: Any) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        profile = getattr(user, "profile", None)
        if not isinstance(profile, Profile):
            return False
        return profile.auth_stage == AuthenticationStage.VIDEO_VERIFIED
