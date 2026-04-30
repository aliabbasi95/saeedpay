from django.urls import include, path

urlpatterns = [
    path("public/", include("apps.contact.api.public.urls")),
]
