# apps/wallets/api/public/urls.py
from django.urls import include, path

urlpatterns = [
    path("public/", include("apps.wallets.api.public.urls")),
    path("internal/", include("apps.wallets.api.internal.urls")),
    path("partner/", include("apps.wallets.api.partner.urls")),
]
