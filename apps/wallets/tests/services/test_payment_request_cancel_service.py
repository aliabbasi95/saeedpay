# wallets/tests/services/test_payment_request_cancel_service.py

import pytest
from rest_framework.exceptions import ValidationError

from merchants.models import Merchant
from store.models import Store
from wallets.models import PaymentEvent, PaymentRequest
from wallets.services.payment.payment_request_service import cancel_payment_request
from wallets.utils.choices import (
    PaymentEventType,
    PaymentFlowType,
    PaymentRequestStatus,
)


@pytest.mark.django_db
class TestCancelPaymentRequestService:
    def test_cancel_payment_request_success(
        self,
        merchant_user,
        store,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=87500,
            description="service cancel test",
            flow_type=PaymentFlowType.QR_POS,
            status=PaymentRequestStatus.CREATED,
        )

        result = cancel_payment_request(
            payment_request=payment_request,
            store=store,
            actor=merchant_user,
        )

        payment_request.refresh_from_db()

        assert result.id == payment_request.id
        assert payment_request.status == PaymentRequestStatus.CANCELLED

        event = PaymentEvent.objects.filter(
            payment_request=payment_request,
            event_type=PaymentEventType.PAYMENT_CANCELLED,
        ).latest("id")

        assert event.actor == merchant_user
        assert event.from_status == PaymentRequestStatus.CREATED
        assert event.to_status == PaymentRequestStatus.CANCELLED

    def test_cancel_payment_request_is_idempotent_for_already_cancelled(
        self,
        merchant_user,
        store,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=87500,
            flow_type=PaymentFlowType.QR_POS,
            status=PaymentRequestStatus.CANCELLED,
        )

        result = cancel_payment_request(
            payment_request=payment_request,
            store=store,
            actor=merchant_user,
        )

        payment_request.refresh_from_db()

        assert result.status == PaymentRequestStatus.CANCELLED
        assert payment_request.status == PaymentRequestStatus.CANCELLED

    def test_cancel_payment_request_for_other_store_raises_validation_error(
        self,
        merchant_user,
        store,
        user_factory,
    ):
        other_user = user_factory("other_merchant_for_cancel_service")
        other_merchant = Merchant.objects.create(user=other_user)
        other_store = Store.objects.create(
            merchant=other_merchant,
            name="other-store",
        )
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=87500,
            flow_type=PaymentFlowType.QR_POS,
            status=PaymentRequestStatus.CREATED,
        )

        with pytest.raises(ValidationError) as exc:
            cancel_payment_request(
                payment_request=payment_request,
                store=other_store,
                actor=other_user,
            )

        assert exc.value.get_codes() == ["forbidden_store"]

    def test_cancel_completed_payment_request_raises_validation_error(
        self,
        merchant_user,
        store,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=87500,
            flow_type=PaymentFlowType.QR_POS,
            status=PaymentRequestStatus.COMPLETED,
        )

        with pytest.raises(ValidationError) as exc:
            cancel_payment_request(
                payment_request=payment_request,
                store=store,
                actor=merchant_user,
            )

        assert exc.value.get_codes() == ["not_cancellable"]

    def test_cancel_expired_payment_request_raises_validation_error(
        self,
        merchant_user,
        store,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=None,
            amount=87500,
            flow_type=PaymentFlowType.QR_POS,
            status=PaymentRequestStatus.EXPIRED,
        )

        with pytest.raises(ValidationError) as exc:
            cancel_payment_request(
                payment_request=payment_request,
                store=store,
                actor=merchant_user,
            )

        assert exc.value.get_codes() == ["not_cancellable"]
