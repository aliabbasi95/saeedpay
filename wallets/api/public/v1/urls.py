# wallets/api/public/v1/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from wallets.api.public.v1.views import (
    InstallmentViewSet,
    InstallmentPlanViewSet,
    PaymentRequestViewSet,
    WalletTransferViewSet,
    WalletViewSet,
)

app_name = "wallets_public_v1"

router = DefaultRouter()
router.register("wallets", WalletViewSet, basename="wallet")
router.register(
    "payment-requests", PaymentRequestViewSet, basename="payment-request"
)
router.register(
    "wallet-transfers", WalletTransferViewSet, basename="wallet-transfer"
)
router.register(
    "installment-plans", InstallmentPlanViewSet, basename="installment-plan"
)
router.register("installments", InstallmentViewSet, basename="installment")

urlpatterns = [
    path("", include(router.urls)),
]
