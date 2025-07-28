# wallets/api/internal/v1/urls.py
from django.urls import path

from wallets.api.internal.v1.views import \
    InternalCustomerWalletListByNationalIdView

app_name = "wallets_internal_v1"

urlpatterns = [
    path(
        "wallets/",
        InternalCustomerWalletListByNationalIdView.as_view(),
        name="wallet-list"
    ),
]
