from django.urls import include, path

urlpatterns = [
    path("public/", include("credit.api.public.urls")),
]
