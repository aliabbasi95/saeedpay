# wallets/tests/models/test_payment_request.py

from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from wallets.models import PaymentRequest
from wallets.utils.choices import PaymentRequestStatus


@pytest.mark.django_db
class TestPaymentRequestModel:

    def test_reference_code_generated_on_save(self, store):
        pr = PaymentRequest.objects.create(
            store=store, amount=1000, return_url="https://example.com"
        )
        assert pr.reference_code
        assert pr.status == PaymentRequestStatus.CREATED
        assert pr.expires_at is not None

    def test_mark_methods_and_rollback_calls(self, store):
        pr = PaymentRequest.objects.create(
            store=store, amount=2000, return_url="https://site.com"
        )
        pr.mark_awaiting_merchant()
        assert pr.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION

        pr.mark_completed()
        assert pr.status == PaymentRequestStatus.COMPLETED

        with patch(
                "wallets.services.payment.rollback_payment"
        ) as rollback_mock:
            pr.mark_cancelled()
            assert pr.status == PaymentRequestStatus.CANCELLED
            assert rollback_mock.called

        with patch(
                "wallets.services.payment.rollback_payment"
        ) as rollback_mock:
            pr.mark_expired()
            assert pr.status == PaymentRequestStatus.EXPIRED
            assert rollback_mock.called

    def test_str(self, store):
        pr = PaymentRequest.objects.create(
            store=store, amount=12345, return_url="https://test.com"
        )
        s = str(pr)
        assert "درخواست پرداخت #" in s
        assert store.name in s

    def test_reference_code_uniqueness(self, store):
        codes = set()
        for i in range(10):
            pr = PaymentRequest.objects.create(
                store=store, amount=1000 + i, return_url=f"https://{i}.com"
            )
            assert pr.reference_code not in codes
            codes.add(pr.reference_code)

    def test_manual_reference_code_not_overwritten(self, store):
        pr = PaymentRequest(
            store=store, amount=1500, return_url="https://manual.com",
            reference_code="CUSTOM123"
        )
        pr.save()
        assert pr.reference_code == "CUSTOM123"

    def test_reference_code_persists_after_save(self, store):
        pr = PaymentRequest.objects.create(
            store=store, amount=3000, return_url="https://persist.com"
        )
        orig = pr.reference_code
        pr.amount = 4000
        pr.save()
        pr.refresh_from_db()
        assert pr.reference_code == orig

    def test_missing_required_fields_and_invalid_url(self, store):
        pr = PaymentRequest(store=store, amount=2000)
        with pytest.raises(ValidationError):
            pr.full_clean()

        pr2 = PaymentRequest(store=store, amount=1234, return_url="not_a_url")
        with pytest.raises(ValidationError):
            pr2.full_clean()

    def test_expires_at_can_be_set(self, store):
        now = timezone.now()
        pr = PaymentRequest.objects.create(
            store=store, amount=8888, return_url="https://expire.com",
            expires_at=now
        )
        assert pr.expires_at == now

    def test_store_cascade_delete(self, store):
        pr = PaymentRequest.objects.create(
            store=store, amount=1300, return_url="https://del.com"
        )
        pr_id = pr.id
        store.delete()
        assert not PaymentRequest.objects.filter(id=pr_id).exists()

    def test_update_optional_fields(self, store):
        pr = PaymentRequest.objects.create(
            store=store, amount=9000, return_url="https://update.com",
            description="desc"
        )
        assert pr.description == "desc"
        pr.description = "updated desc"
        pr.save()
        pr.refresh_from_db()
        assert pr.description == "updated desc"

    def test_duplicate_reference_code_fails(self, store):
        PaymentRequest.objects.create(
            store=store, amount=1000, return_url="https://dup.com",
            reference_code="DUPLICATECODE"
        )
        with pytest.raises(Exception):
            PaymentRequest.objects.create(
                store=store, amount=1001, return_url="https://dup.com",
                reference_code="DUPLICATECODE"
            )

    def test_paid_by_and_paid_wallet_fields(
            self, store, customer_user, customer_cash_wallet
    ):
        pr = PaymentRequest.objects.create(
            store=store, amount=700, return_url="https://paid.com",
            paid_by=customer_user, paid_wallet=customer_cash_wallet
        )
        assert pr.paid_by == customer_user
        assert pr.paid_wallet == customer_cash_wallet

    def test_status_choice_validation(self, store):
        pr = PaymentRequest(
            store=store, amount=333, return_url="https://ok.com",
            status="NOT_A_REAL_STATUS"
        )
        with pytest.raises(ValidationError):
            pr.full_clean()

    def test_reference_code_max_length(self, store):
        code = "A" * 20
        pr = PaymentRequest.objects.create(
            store=store, amount=5000, return_url="https://len.com",
            reference_code=code
        )
        assert pr.reference_code == code

    def test_external_guid_uniqueness_per_store(self, store):
        pr1 = PaymentRequest.objects.create(
            store=store, amount=100, return_url="https://ok.com",
            external_guid="GUID-1"
        )
        assert pr1.external_guid == "GUID-1"
        with pytest.raises(Exception):
            PaymentRequest.objects.create(
                store=store, amount=200, return_url="https://ok2.com",
                external_guid="GUID-1"
            )

    def test_external_guid_can_repeat_on_other_store(
            self, store, merchant_user
    ):
        from store.models import Store
        store2 = Store.objects.create(name="store-2", merchant=store.merchant)

        guid = "ORD-1234"
        pr1 = PaymentRequest.objects.create(
            store=store, amount=10_000, return_url="https://ok.com",
            external_guid=guid,
        )
        assert pr1.external_guid == guid

        pr2 = PaymentRequest.objects.create(
            store=store2, amount=20_000, return_url="https://ok2.com",
            external_guid=guid,
        )
        assert pr2.external_guid == guid
