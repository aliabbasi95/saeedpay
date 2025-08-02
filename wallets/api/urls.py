# wallets/api/public/urls.py
from django.urls import include, path

urlpatterns = [
    path('public/', include('wallets.api.public.urls')),
    path('internal/', include('wallets.api.internal.urls')),
    path('partner/', include('wallets.api.partner.urls')),
]
