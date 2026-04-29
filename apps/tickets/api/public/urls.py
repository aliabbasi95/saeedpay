# tickets/api/public/urls.py
from django.urls import include, path

urlpatterns = [
    path("v1/", include("tickets.api.public.v1.urls")),
]
