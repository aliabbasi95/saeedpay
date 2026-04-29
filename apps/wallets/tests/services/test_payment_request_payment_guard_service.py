# wallets/tests/services/test_payment_request_payment_guard_service.py

import pytest
from rest_framework.exceptions import ValidationError

from wallets.models import Payment, PaymentRequest
from wallets.services.payment.payment_request_service import (
    ensure_no_active_payment_exists,
)
from wallets.utils.choices import (
    PaymentFlowType,
    PaymentMethod,
    PaymentRequestStatus,
    PaymentStatus,
)


@pytest.mark.django_db
class TestPaymentRequestPaymentGuardService:
    def test_ensure_no_active_payment_exists_raises_for_completed_payment(
        self,
        customer_user,
        customer_cash_wallet,
        store,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=87500,
            flow_type=PaymentFlowType.ONLINE,
            status=PaymentRequestStatus.COMPLETED,
            return_url="https://example.com/return",
            external_guid="ORD-COMPLETED-1",
        )
        Payment.objects.create(
            payment_request=payment_request,
            payer=customer_user,
            payer_wallet=customer_cash_wallet,
            amount=payment_request.amount,
            method=PaymentMethod.CASH,
            flow_type=payment_request.flow_type,
            status=PaymentStatus.COMPLETED,
        )

        with pytest.raises(ValidationError) as exc:
            ensure_no_active_payment_exists(payment_request)

        assert exc.value.get_codes() == ["already_completed"]

    def test_ensure_no_active_payment_exists_raises_for_active_payment(
        self,
        customer_user,
        customer_cash_wallet,
        store,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=87500,
            flow_type=PaymentFlowType.ONLINE,
            status=PaymentRequestStatus.CREATED,
            return_url="https://example.com/return",
            external_guid="ORD-ACTIVE-1",
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

        with pytest.raises(ValidationError) as exc:
            ensure_no_active_payment_exists(payment_request)

        assert exc.value.get_codes() == ["payment_in_progress"]

    def test_ensure_no_active_payment_exists_passes_when_no_blocking_payment(
        self,
        store,
        customer,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer,
            amount=87500,
            flow_type=PaymentFlowType.QR_POS,
            status=PaymentRequestStatus.CREATED,
        )

        result = ensure_no_active_payment_exists(payment_request)

        assert result is None
