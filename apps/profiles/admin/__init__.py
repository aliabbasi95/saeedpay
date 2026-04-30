# apps/profiles/admin/__init__.py

from .kyc_attempt import ProfileKYCAttemptAdmin
from .kyc_video_asset import KYCVideoAssetAdmin
from .profile import ProfileAdmin

__all__ = [
    "KYCVideoAssetAdmin",
    "ProfileAdmin",
    "ProfileKYCAttemptAdmin",
]
