from django.urls import path, include

urlpatterns = [
    path("public/", include("customers.api.public.urls")),
]
