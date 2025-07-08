# wallets/api/internal/urls.py
from django.urls import include, path

urlpatterns = [
    path('v1/', include('wallets.api.internal.v1.urls')),
]
