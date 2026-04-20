from django.urls import include, path

urlpatterns = [
    path("v1/", include("credit.api.public.v1.urls")),
]
