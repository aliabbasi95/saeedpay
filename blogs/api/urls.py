# blogs/api/urls.py
from django.urls import include, path

urlpatterns = [
    path("public/", include("blogs.api.public.urls")),
]
