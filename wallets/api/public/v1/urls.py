# wallets/api/public/v1/urls.py
from django.urls import path

from wallets.api.public.v1.views import WalletListView

app_name = "wallets_public_v1"

urlpatterns = [
    path(
        "wallets/",
        WalletListView.as_view(),
        name="wallet-list"
    ),
]
