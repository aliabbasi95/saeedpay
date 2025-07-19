# wallets/tests/models/test_payment_request.py
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from wallets.models import PaymentRequest
from wallets.utils.choices import PaymentRequestStatus


@pytest.mark.django_db
class TestPaymentRequestModel:

    def test_reference_code_generated_on_save(self):
        user = get_user_model().objects.create(username="merchant")
        pr = PaymentRequest.objects.create(
            merchant=user, amount=1000, return_url="https://example.com"
        )
        assert pr.reference_code
        assert pr.status == PaymentRequestStatus.CREATED

    def test_mark_methods(self):
        user = get_user_model().objects.create(username="merchant2")
        pr = PaymentRequest.objects.create(
            merchant=user, amount=2000, return_url="https://site.com"
        )
        pr.mark_awaiting_merchant()
        assert pr.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        pr.mark_completed()
        assert pr.status == PaymentRequestStatus.COMPLETED
        pr.mark_cancelled()
        assert pr.status == PaymentRequestStatus.CANCELLED
        pr.mark_expired()
        assert pr.status == PaymentRequestStatus.EXPIRED

    def test_str(self):
        user = get_user_model().objects.create(username="merchant3")
        pr = PaymentRequest.objects.create(
            merchant=user, amount=12345, return_url="https://test.com"
        )
        assert str(pr).startswith("درخواست پرداخت #")

    def test_reference_code_uniqueness(self):
        user = get_user_model().objects.create(username="merchant_u")
        codes = set()
        for i in range(10):
            pr = PaymentRequest.objects.create(
                merchant=user, amount=1000 + i, return_url=f"https://{i}.com"
            )
            assert pr.reference_code not in codes
            codes.add(pr.reference_code)

    def test_manual_reference_code_not_overwritten(self):
        user = get_user_model().objects.create(username="manual")
        pr = PaymentRequest(
            merchant=user, amount=1500, return_url="https://manual.com",
            reference_code="CUSTOM123"
        )
        pr.save()
        assert pr.reference_code == "CUSTOM123"

    def test_reference_code_persists_after_save(self):
        user = get_user_model().objects.create(username="multi")
        pr = PaymentRequest.objects.create(
            merchant=user, amount=3000, return_url="https://persist.com"
        )
        orig_code = pr.reference_code
        pr.amount = 4000
        pr.save()
        pr.refresh_from_db()
        assert pr.reference_code == orig_code

    def test_status_methods_and_rerun(self):
        user = get_user_model().objects.create(username="retest")
        pr = PaymentRequest.objects.create(
            merchant=user, amount=2000, return_url="https://site.com"
        )
        pr.mark_completed()
        pr.mark_completed()
        assert pr.status == PaymentRequestStatus.COMPLETED
        pr.mark_expired()
        pr.mark_expired()
        assert pr.status == PaymentRequestStatus.EXPIRED

    def test_missing_required_fields(self):
        user = get_user_model().objects.create(username="nofield")
        with pytest.raises(ValidationError):
            pr = PaymentRequest(merchant=user, amount=2000)
            pr.full_clean()
        with pytest.raises(ValidationError):
            pr = PaymentRequest(
                merchant=user, amount=-1, return_url="https://bad.com"
            )
            pr.full_clean()

    def test_str(self):
        user = get_user_model().objects.create(username="merchant3")
        pr = PaymentRequest.objects.create(
            merchant=user, amount=12345, return_url="https://test.com"
        )
        assert str(pr).startswith("درخواست پرداخت #")

    def test_expires_at(self):
        import datetime
        user = get_user_model().objects.create(username="expire_test")
        pr = PaymentRequest.objects.create(
            merchant=user,
            amount=8888,
            return_url="https://expire.com",
            expires_at=datetime.datetime.now()
        )
        assert pr.expires_at

    def test_rollback_called_on_cancel_and_expire(self):
        user = get_user_model().objects.create(username="mock_rollback")
        pr = PaymentRequest.objects.create(
            merchant=user, amount=1000, return_url="https://mock.com"
        )
        with patch(
                "wallets.services.payment.rollback_payment"
        ) as rollback_mock:
            pr.mark_cancelled()
            assert rollback_mock.called
        with patch(
                "wallets.services.payment.rollback_payment"
        ) as rollback_mock:
            pr.mark_expired()
            assert rollback_mock.called

    def test_invalid_url(self):
        user = get_user_model().objects.create(username="inv_url")
        pr = PaymentRequest(merchant=user, amount=1234, return_url="not_a_url")
        with pytest.raises(ValidationError):
            pr.full_clean()

    def test_merchant_deletion_cascade(self):
        user = get_user_model().objects.create(username="merchant_del")
        pr = PaymentRequest.objects.create(
            merchant=user, amount=1300, return_url="https://del.com"
        )
        pr_id = pr.id
        user.delete()
        # حالا باید مطمئن شویم PaymentRequest هم حذف شده
        assert not PaymentRequest.objects.filter(id=pr_id).exists()

    def test_optional_and_update_fields(self):
        import datetime
        user = get_user_model().objects.create(username="opt_user")
        pr = PaymentRequest.objects.create(
            merchant=user, amount=9000, return_url="https://update.com",
            description="desc", expires_at=datetime.datetime.now()
        )
        assert pr.description == "desc"
        assert pr.expires_at is not None

        pr.description = "updated desc"
        pr.save()
        pr.refresh_from_db()
        assert pr.description == "updated desc"

    def test_reference_code_duplicate(self):
        user = get_user_model().objects.create(username="dupuser")
        pr1 = PaymentRequest.objects.create(
            merchant=user, amount=1000, return_url="https://dup.com",
            reference_code="DUPLICATECODE"
        )
        with pytest.raises(Exception):
            PaymentRequest.objects.create(
                merchant=user, amount=1001, return_url="https://dup.com",
                reference_code="DUPLICATECODE"
            )

    def test_paid_by_and_paid_wallet_fields(self):
        user = get_user_model().objects.create(username="paiduser")
        from wallets.models import Wallet
        wallet = Wallet.objects.create(
            user=user, kind="micro_credit", owner_type="customer",
            balance=10000
            )
        pr = PaymentRequest.objects.create(
            merchant=user, amount=700, return_url="https://paid.com",
            paid_by=user, paid_wallet=wallet
        )
        assert pr.paid_by == user
        assert pr.paid_wallet == wallet

    def test_invalid_status_assignment(self):
        user = get_user_model().objects.create(username="badstatus")
        pr = PaymentRequest(
            merchant=user, amount=333, return_url="https://badstatus.com",
            status="NOT_A_REAL_STATUS"
        )
        with pytest.raises(ValidationError):
            pr.full_clean()

    def test_reference_code_max_length(self):
        user = get_user_model().objects.create(username="maxlen")
        code = "A" * 20
        pr = PaymentRequest.objects.create(
            merchant=user, amount=5000, return_url="https://len.com",
            reference_code=code
        )
        assert pr.reference_code == code
