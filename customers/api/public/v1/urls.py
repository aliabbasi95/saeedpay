# customers/api/public/v1/urls.py
from django.urls import path

from .views.auth import SendOTPView, RegisterView, LoginView

app_name = "customers_public_v1"

urlpatterns = [
    path("send-otp/", SendOTPView.as_view(), name="send-otp"),
    path("register/", RegisterView.as_view(), name="customer-register"),
    path("login/", LoginView.as_view(), name="customer-login"),
]
