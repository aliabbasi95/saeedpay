from django.urls import include, path

app_name = "kyc"

urlpatterns = [
    path("public/", include("kyc.api.public.urls")),
]
