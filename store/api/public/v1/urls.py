# store/api/public/v1/urls.py
from django.urls import path


from store.api.public.v1.views import StoreApiKeyRegenerateView

app_name = "store_public_v1"

urlpatterns = [
    path(
        "regenerate-api-key/",
        StoreApiKeyRegenerateView.as_view(),
        name="regenerate-api-key"
    ),
]
