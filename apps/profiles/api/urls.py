# apps/profiles/api/public/urls.py
from django.urls import include, path

urlpatterns = [
    path("public/", include("apps.profiles.api.public.urls")),
]
