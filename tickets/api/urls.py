# tickets/api/urls.py
from django.urls import include, path

urlpatterns = [
    path("public/", include("tickets.api.public.urls")),
]
