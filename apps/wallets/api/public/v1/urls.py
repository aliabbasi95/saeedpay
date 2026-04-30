# apps/wallets/api/public/v1/urls.py

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.wallets.api.public.v1.views import (
    InstallmentPlanViewSet,
    InstallmentViewSet,
    MerchantPosPaymentRequestViewSet,
    PaymentRequestViewSet,
    WalletTransferViewSet,
    WalletViewSet,
)

app_name = "wallets_public_v1"

router = DefaultRouter()
router.register("wallets", WalletViewSet, basename="wallet")
router.register(
    "payment-requests",
    PaymentRequestViewSet,
    basename="payment-request",
)
router.register(
    "merchant/pos/payment-requests",
    MerchantPosPaymentRequestViewSet,
    basename="merchant-pos-payment-request",
)
router.register(
    "wallet-transfers",
    WalletTransferViewSet,
    basename="wallet-transfer",
)
router.register(
    "installment-plans",
    InstallmentPlanViewSet,
    basename="installment-plan",
)
router.register("installments", InstallmentViewSet, basename="installment")

urlpatterns = [
    path("", include(router.urls)),
]
