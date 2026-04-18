# banking/api/urls.py

from django.urls import include, path

app_name = "banking"

urlpatterns = [
    path("v1/", include("banking.api.public.v1.urls", namespace="v1")),
]
