# wallets/api/public/v1/urls.py
from django.urls import path

from wallets.api.public.v1.views import (
    WalletListView,
    PaymentRequestCreateView,
    PaymentRequestDetailView,
    PaymentConfirmView,
    PaymentRequestVerifyView,
    WalletTransferConfirmView,
    WalletTransferRejectView,
    WalletTransferListCreateView, InstallmentRequestCreateView,
    InstallmentRequestDetailView, InstallmentRequestConfirmView,
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
        "installment-request/",
        InstallmentRequestCreateView.as_view(),
        name="installment-request-create"
    ),
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
