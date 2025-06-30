"""
URL configuration for saeedpay project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.shortcuts import redirect
from django.urls import path, include

from lib.cas_auth.admin.utils import has_admin_permission

urlpatterns_main = [
    path("admin/", admin.site.urls),
    path("cas-auth/", include("lib.cas_auth.urls")),
]

api_urlpatterns = [
    path("api/auth/", include("auth_api.api.urls")),
]

urlpatterns_main = urlpatterns_main + api_urlpatterns

if not settings.CAS_DEBUG:
    urlpatterns_main.append(
        path(
            "admin/login/",
            lambda request: redirect(
                f'/cas/users/user-login/?next={request.META.get("HTTP_REFERER", "/saeedpay/admin/")}&service_name=SAEEDPAY',
            ),
        ),
    )

urlpatterns = [
    path("saeedpay/", include(urlpatterns_main)),
]

admin.autodiscover()
admin.site.enable_nav_sidebar = False
admin.site.has_permission = has_admin_permission
admin.site.index_title = "Saeed Pay"
