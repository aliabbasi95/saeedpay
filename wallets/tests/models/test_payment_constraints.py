# wallets/tests/models/test_payment_constraints.py

import pytest
from django.db import IntegrityError

from wallets.models import Payment, PaymentRequest
from wallets.utils.choices import (
    PaymentFlowType,
    PaymentMethod,
    PaymentRequestStatus,
    PaymentStatus,
)


@pytest.mark.django_db
class TestPaymentConstraints:

    def test_cannot_create_second_active_payment_for_same_request(
            self,
            customer_user,
            customer_cash_wallet,
            store,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=50_000,
            flow_type=PaymentFlowType.ONLINE,
            status=PaymentRequestStatus.CREATED,
            return_url="https://example.com/return",
            external_guid="ORD-CONSTRAINT-1",
        )

        Payment.objects.create(
            payment_request=payment_request,
            payer=customer_user,
            payer_wallet=customer_cash_wallet,
            amount=payment_request.amount,
            method=PaymentMethod.CASH,
            flow_type=payment_request.flow_type,
            status=PaymentStatus.CREATED,
        )

        with pytest.raises(IntegrityError):
            Payment.objects.create(
                payment_request=payment_request,
                payer=customer_user,
                payer_wallet=customer_cash_wallet,
                amount=payment_request.amount,
                method=PaymentMethod.CASH,
                flow_type=payment_request.flow_type,
                status=PaymentStatus.AUTHORIZED,
            )
