# apps/auth_api/api/public/urls.py
from django.urls import include, path

urlpatterns = [
    path("v1/", include("apps.auth_api.api.public.v1.urls")),
]
