from django.urls import path, include

urlpatterns = [
    path("public/", include("credit.api.public.urls")),
]
