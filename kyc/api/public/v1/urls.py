from django.urls import path
from .views import (
    IdentityVerificationView,
    VideoVerificationSubmitView,
    VideoVerificationPollView
)

app_name = 'kyc_public_v1'

urlpatterns = [
    path('verify-identity/', IdentityVerificationView.as_view(), name='verify_identity'),
    path('submit-video-verification/', VideoVerificationSubmitView.as_view(), name='submit_video_verification'),
    path('poll-video-verification/', VideoVerificationPollView.as_view(), name='poll_video_verification'),
]
