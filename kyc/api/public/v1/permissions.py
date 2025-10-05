# kyc/api/public/v1/permissions.py

from rest_framework.permissions import BasePermission
from profiles.models import Profile
from profiles.utils.choices import AuthenticationStage


class IsIdentityVerified(BasePermission):
    """
    Permission class that checks if the user's profile is in IDENTITY_VERIFIED stage.
    This is required for video verification submission.
    """
    
    def has_permission(self, request, view):
        # Check if user is authenticated first
        if not request.user or not request.user.is_authenticated:
            return False
            
        # Get user's profile
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return False
            
        # Check if profile is in IDENTITY_VERIFIED stage
        return profile.auth_stage == AuthenticationStage.IDENTITY_VERIFIED


class IsVideoVerified(BasePermission):
    """
    Permission class that checks if the user's profile is in VIDEO_VERIFIED stage.
    This would be used for endpoints that require video verification to be completed.
    """
    
    def has_permission(self, request, view):
        # Check if user is authenticated first
        if not request.user or not request.user.is_authenticated:
            return False
            
        # Get user's profile
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return False
            
        # Check if profile is in VIDEO_VERIFIED stage
        return profile.auth_stage == AuthenticationStage.VIDEO_VERIFIED
