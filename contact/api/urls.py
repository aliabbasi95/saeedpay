from django.urls import include, path

urlpatterns = [
    path("public/", include("contact.api.public.urls")),
]
