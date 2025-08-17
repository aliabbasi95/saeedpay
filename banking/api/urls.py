# banking/api/urls.py

from django.urls import path, include

app_name = "banking"

urlpatterns = [
    path("v1/", include("banking.api.public.v1.urls", namespace="v1")),
]
