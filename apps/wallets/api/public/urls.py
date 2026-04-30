# apps/wallets/api/public/urls.py
from django.urls import include, path

urlpatterns = [
    path("v1/", include("apps.wallets.api.public.v1.urls")),
]
