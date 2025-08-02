# wallets/api/public/v1/urls.py
from django.urls import path

from wallets.api.public.v1.views import (
    WalletListView,
    PaymentRequestDetailView,
    PaymentConfirmView,
    WalletTransferConfirmView,
    WalletTransferRejectView,
    WalletTransferListCreateView,
    InstallmentRequestDetailView,
    InstallmentRequestConfirmView,
    InstallmentCalculationView,
)

app_name = "wallets_public_v1"

urlpatterns = [
    path(
        "wallets/",
        WalletListView.as_view(),
        name="wallet-list"
    ),
    # payment

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

    # transfer
    path(
        'wallet-transfer/', WalletTransferListCreateView.as_view(),
        name='wallet-transfer-list-create'
    ),
    path(
        'wallet-transfer/<int:pk>/confirm/',
        WalletTransferConfirmView.as_view(),
        name='wallet-transfer-confirm'
    ),
    path(
        'wallet-transfer/<int:pk>/reject/',
        WalletTransferRejectView.as_view(),
        name='wallet-transfer-reject'
    ),
    # installment

    path(
        "installment-request/<str:reference_code>/",
        InstallmentRequestDetailView.as_view(),
        name="installment-request-detail"
    ),
    path(
        "installment-request/<str:reference_code>/calculate/",
        InstallmentCalculationView.as_view(),
        name="installment-request-calculate"
    ),
    path(
        "installment-request/<str:reference_code>/confirm/",
        InstallmentRequestConfirmView.as_view(),
        name="installment-request-confirm"
    ),

]
