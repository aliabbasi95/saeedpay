# apps/store/api/public/urls.py

from django.urls import include, path

urlpatterns = [
    path("public/", include("apps.store.api.public.urls")),
]
