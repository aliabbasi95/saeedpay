from django.urls import include, path

urlpatterns = [
    path("public/", include("apps.credit.api.public.urls")),
]
