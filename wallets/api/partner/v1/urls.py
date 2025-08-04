# wallets/api/partner/v1/urls.py
from django.urls import path

from wallets.api.partner.v1.views import (
    PaymentRequestCreateView,
    PaymentRequestVerifyView,
    InstallmentRequestCreateView,
    InstallmentRequestVerifyView, InstallmentRequestRetrieveView,
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
        "payment-request/<str:reference_code>/verify/",
        PaymentRequestVerifyView.as_view(),
        name="payment-request-verify"
    ),
    # installment
    path(
        "installment-request/",
        InstallmentRequestCreateView.as_view(),
        name="installment-request-create"
    ),
    path(
        "installment-request/<str:reference_code>/verify/",
        InstallmentRequestVerifyView.as_view(),
        name="installment-request-verify"
    ),
    path(
        "installment-request/<str:reference_code>/",
        InstallmentRequestRetrieveView.as_view(),
        name="installment-request-retrieve"
        ),
]
