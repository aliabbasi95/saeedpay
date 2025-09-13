from django.urls import path
from .views.identity_verification import IdentityVerificationView

app_name = 'kyc_public_v1'

urlpatterns = [
    path('verify-identity/', IdentityVerificationView.as_view(), name='verify_identity'),
]
