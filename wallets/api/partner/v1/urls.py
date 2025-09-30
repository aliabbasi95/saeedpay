# wallets/api/partner/v1/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from wallets.api.partner.v1.views import PartnerPaymentRequestViewSet

app_name = "wallets_partner_v1"

router = DefaultRouter()
router.register(
    "payment-requests", PartnerPaymentRequestViewSet,
    basename="partner-payment-request"
)

urlpatterns = [
    path("", include(router.urls)),
]
