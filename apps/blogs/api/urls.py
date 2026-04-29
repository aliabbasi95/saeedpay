# apps/blogs/api/urls.py

from django.urls import include, path

urlpatterns = [
    path("public/", include("apps.blogs.api.public.urls")),
]
