# apps/tickets/api/urls.py
from django.urls import include, path

urlpatterns = [
    path("public/", include("apps.tickets.api.public.urls")),
]
