# wallets/api/partner/urls.py
from django.urls import include, path

urlpatterns = [
    path('v1/', include('wallets.api.partner.v1.urls')),
]
