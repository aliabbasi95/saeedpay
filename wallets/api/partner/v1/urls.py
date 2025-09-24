# wallets/api/partner/v1/urls.py
from django.urls import path

from wallets.api.partner.v1.views import (
    PaymentRequestCreateView,
    PaymentRequestVerifyView,
    PaymentRequestRetrieveView,
)

app_name = "wallets_partner_v1"

urlpatterns = [
    # payment
    path(
        "payment-request/",
        PaymentRequestCreateView.as_view(),
        name="payment-request-create"
    ),
    path(
        "payment-request/<str:reference_code>/",
        PaymentRequestRetrieveView.as_view(),
        name="payment-request-detail"
    ),
    path(
        "payment-request/<str:reference_code>/verify/",
        PaymentRequestVerifyView.as_view(),
        name="payment-request-verify"
    ),

]
