# wallets/tests/public/v1/views/test_payment_concurrency_api.py

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from auth_api.models import PhoneOTP
from wallets.models import Payment, PaymentRequest, Wallet
from wallets.utils.choices import (
    OwnerType,
    PaymentFlowType,
    PaymentMethod,
    PaymentRequestStatus,
    PaymentStatus,
    WalletKind,
)


@pytest.mark.django_db
class TestPaymentConcurrencyApi:
    def test_qr_confirm_returns_payment_in_progress_when_active_payment_exists(
        self,
        store,
        customer_user,
        customer_cash_wallet,
        monkeypatch,
    ):
        merchant_wallet, _ = Wallet.objects.get_or_create(
            user=store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
            defaults={"balance": 0},
        )
        assert merchant_wallet is not None

        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=12_345,
            flow_type=PaymentFlowType.QR_POS,
            status=PaymentRequestStatus.CREATED,
        )

        Payment.objects.create(
            payment_request=payment_request,
            payer=customer_user,
            payer_wallet=customer_cash_wallet,
            amount=payment_request.amount,
            method=PaymentMethod.CASH,
            flow_type=payment_request.flow_type,
            status=PaymentStatus.AUTHORIZED,
        )

        otp = PhoneOTP.objects.create(phone_number=customer_user.profile.phone_number)
        monkeypatch.setattr(otp, "verify", lambda code: True)
        monkeypatch.setattr(PhoneOTP.objects, "get", lambda **kwargs: otp)

        client = APIClient()
        client.force_authenticate(user=customer_user)

        url = reverse(
            "wallets_public_v1:payment-request-confirm",
            args=[payment_request.reference_code],
        )
        response = client.post(
            url,
            {
                "wallet_id": customer_cash_wallet.id,
                "code": "1234",
            },
            format="json",
        )

        assert response.status_code == 400, response.data
        assert response.data["code"] == "payment_in_progress"
