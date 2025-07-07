# auth_api/api/public/v1/urls.py
from django.urls import path

from auth_api.api.public.v1.views import (
    LoginView,
    RegisterCustomerView,
    SendOTPView,
    LogoutView,
    SecureTokenRefreshView,
)

app_name = "auth_api_public_v1"

urlpatterns = [
    path(
        "send-otp/",
        SendOTPView.as_view(),
        name="send-otp"
    ),
    path(
        "register/customer/",
        RegisterCustomerView.as_view(),
        name="register-customer"
    ),
    path(
        "login/",
        LoginView.as_view(),
        name="login"
    ),
    path(
        "logout/",
        LogoutView.as_view(),
        name="logout"
    ),
    path(
        "token/refresh/",
        SecureTokenRefreshView.as_view(),
        name="token-refresh"
    ),
]
