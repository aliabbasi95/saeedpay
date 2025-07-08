# wallets/api/internal/v1/urls.py
from django.urls import path

from wallets.api.internal.v1.views import InternalCustomerWalletListView

app_name = "wallets_internal_v1"

urlpatterns = [
    path(
        "wallets/",
        InternalCustomerWalletListView.as_view(),
        name="wallet-list"
    ),
]
