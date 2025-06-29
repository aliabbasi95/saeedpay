# customers/api/public/v1/urls.py
from django.urls import path

from .views.auth import SendOTPView, RegisterView

urlpatterns = [
    path('send-otp/', SendOTPView.as_view()),
    path('register/', RegisterView.as_view()),
]
