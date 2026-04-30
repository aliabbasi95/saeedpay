# customer/api/public/urls.py
from django.urls import include, path

urlpatterns = [
    path("v1/", include("apps.customers.api.public.v1.urls")),
]
