# apps/tickets/api/public/urls.py
from django.urls import include, path

urlpatterns = [
    path("v1/", include("apps.tickets.api.public.v1.urls")),
]
