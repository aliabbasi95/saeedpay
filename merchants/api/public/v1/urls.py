# merchants/api/public/v1/urls.py
from django.urls import path

from merchants.api.public.v1.views import MerchantApiKeyRegenerateView

app_name = "merchants_public_v1"

urlpatterns = [
    path(
        "regenerate-api-key/",
        MerchantApiKeyRegenerateView.as_view(),
        name="send-otp"
    ),
]
