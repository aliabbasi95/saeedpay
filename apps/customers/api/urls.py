from django.urls import include, path

urlpatterns = [
    path("public/", include("customers.api.public.urls")),
]
