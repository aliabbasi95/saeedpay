from django.urls import include, path

urlpatterns = [
    path("v1/", include("apps.credit.api.public.v1.urls")),
]
