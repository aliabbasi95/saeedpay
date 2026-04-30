from django.urls import include, path

urlpatterns = [
    path("public/", include("apps.customers.api.public.urls")),
]
