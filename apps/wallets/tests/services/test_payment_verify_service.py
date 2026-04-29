# wallets/tests/services/test_payment_verify_service.py

import pytest
from rest_framework.exceptions import ValidationError

from wallets.models import PaymentRequest
from wallets.services.payment.payment_processing_service import verify_payment_request
from wallets.utils.choices import PaymentFlowType, PaymentRequestStatus


@pytest.mark.django_db
class TestVerifyPaymentRequestService:
    def test_verify_payment_request_rejects_qr_pos_flow(
        self,
        store,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=87500,
            flow_type=PaymentFlowType.QR_POS,
            status=PaymentRequestStatus.CREATED,
        )

        with pytest.raises(ValidationError) as exc:
            verify_payment_request(
                payment_request=payment_request,
                store=store,
            )

        assert exc.value.get_codes() == ["unsupported_flow_type"]
