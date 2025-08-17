from django.urls import path, include

urlpatterns = [
    path("v1/", include("credit.api.public.v1.urls")),
]
