# wallets/api/public/v1/urls.py
from django.urls import path

from wallets.api.public.v1.views import (
    WalletListView,
    PaymentRequestCreateView,
    PaymentRequestDetailView, PaymentConfirmView, PaymentRequestVerifyView,
)

app_name = "wallets_public_v1"

urlpatterns = [
    path(
        "wallets/",
        WalletListView.as_view(),
        name="wallet-list"
    ),
    path(
        "payment-request/",
        PaymentRequestCreateView.as_view(),
        name="payment-request-create"
    ),
    path(
        "payment-request/<str:reference_code>/",
        PaymentRequestDetailView.as_view(),
        name="payment-request-detail"
    ),
    path(
        "payment-request/<str:reference_code>/confirm/",
        PaymentConfirmView.as_view(),
        name="payment-request-confirm"
        ),
    path(
        "payment-request/<str:reference_code>/verify/",
        PaymentRequestVerifyView.as_view(),
        name="payment-request-verify"
        ),

]
