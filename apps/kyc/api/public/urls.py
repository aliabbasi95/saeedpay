from django.urls import include, path

app_name = "kyc_public"

urlpatterns = [
    path("v1/", include("apps.kyc.api.public.v1.urls")),
]
