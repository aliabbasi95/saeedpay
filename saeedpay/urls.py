"""
URL configuration for saeedpay project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from rest_framework.permissions import AllowAny

from lib.cas_auth.admin.utils import has_admin_permission


# ───────────────────────────────
# Healthcheck endpoints
# ───────────────────────────────
def healthz(_request):
    """Simple health check: always returns 200 OK."""
    return JsonResponse({"status": "ok"})


def readyz(_request):
    """Readiness check: verifies DB connection is available."""
    try:
        connections["default"].cursor()
        return JsonResponse({"status": "ready"})
    except OperationalError:
        return JsonResponse({"status": "db_down"}, status=500)


# ───────────────────────────────
# Core URL patterns
# ───────────────────────────────
urlpatterns_main = [
    path("admin/", admin.site.urls),
    path("cas-auth/", include("lib.cas_auth.urls")),
]

api_urlpatterns = [
    path("api/auth/", include("auth_api.api.urls")),
    path("api/profiles/", include("profiles.api.urls")),
    path("api/wallets/", include("wallets.api.urls")),
    path("api/store/", include("store.api.urls")),
    path("api/banking/", include("banking.api.urls")),
    path("api/tickets/", include("tickets.api.urls")),
    path("api/chatbot/", include("chatbot.api.urls")),
    path("api/credit/", include("credit.api.urls")),
    path("api/blogs/", include("blogs.api.urls")),
    path("api/customers/", include("customers.api.urls")),
    path("api/contact/", include("contact.api.urls")),
]

schema_urlpatterns = [
    path(
        "api/schema/",
        SpectacularAPIView.as_view(
            permission_classes=[AllowAny], authentication_classes=[]
        ),

        name="schema"
    ),
    path(
        "api/schema/swagger/",
        SpectacularSwaggerView.as_view(url_name="schema", ),
        name="swagger-ui",
    ),
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

urlpatterns_main = urlpatterns_main + api_urlpatterns + schema_urlpatterns

# CAS-based admin login override
if not settings.CAS_DEBUG:
    urlpatterns_main.append(
        path(
            "admin/login/",
            lambda request: redirect(
                f'/cas/users/user-login/?next={request.META.get("HTTP_REFERER", "/saeedpay/admin/")}&service_name=SAEEDPAY',
            ),
        ),
    )

# ───────────────────────────────
# Final urlpatterns
# ───────────────────────────────
urlpatterns = [
    path("saeedpay/", include(urlpatterns_main)),
    path("saeedpay/healthz", healthz),
    path("saeedpay/readyz", readyz),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
    urlpatterns += static(
        "/public_data/",
        document_root="/home/erfan/Projects/saeedpay/public_data"
    )

# Admin customization
admin.autodiscover()
admin.site.enable_nav_sidebar = False
admin.site.has_permission = has_admin_permission
admin.site.index_title = "Saeed Pay"
