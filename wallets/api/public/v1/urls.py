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
    InstallmentPlanListView,
    InstallmentsByPlanView,
    InstallmentListView,
    InstallmentDetailView,
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
    # installment plans
    path(
        "installment-plans/",
        InstallmentPlanListView.as_view(),
        name="installment-plan-list"
    ),
    path(
        "installment-plans/<int:plan_id>/installments/",
        InstallmentsByPlanView.as_view(),
        name="installments-by-plan"
    ),
    # installments
    path(
        "installments/",
        InstallmentListView.as_view(),
        name="installment-list"
    ),
    path(
        "installments/<int:pk>/",
        InstallmentDetailView.as_view(),
        name="installment-detail"
    ),
]
