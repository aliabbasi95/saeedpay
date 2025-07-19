import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from wallets.models import Wallet, PaymentRequest, Transaction
from wallets.utils.choices import TransactionStatus

@pytest.mark.django_db
class TestTransactionModel:

    def create_wallets_and_pr(self):
        user = get_user_model().objects.create(username="txnuser")
        w1 = Wallet.objects.create(user=user, kind="cash", owner_type="customer")
        w2 = Wallet.objects.create(user=user, kind="merchant_gateway", owner_type="merchant")
        pr = PaymentRequest.objects.create(merchant=user, amount=500, return_url="https://ok.com")
        return user, w1, w2, pr

    def test_reference_code_is_unique_and_generated(self):
        user, w1, w2, pr = self.create_wallets_and_pr()
        codes = set()
        for i in range(10):
            t = Transaction.objects.create(
                from_wallet=w1, to_wallet=w2, amount=500 + i, payment_request=pr
            )
            assert t.reference_code not in codes
            codes.add(t.reference_code)
            assert len(t.reference_code) >= 10

    def test_manual_reference_code_not_overwritten(self):
        user, w1, w2, pr = self.create_wallets_and_pr()
        t = Transaction(
            from_wallet=w1, to_wallet=w2, amount=1000,
            payment_request=pr, reference_code="TXN12345"
        )
        t.save()
        assert t.reference_code == "TXN12345"

    def test_reference_code_persists_after_save(self):
        user, w1, w2, pr = self.create_wallets_and_pr()
        t = Transaction.objects.create(from_wallet=w1, to_wallet=w2, amount=1000, payment_request=pr)
        orig_code = t.reference_code
        t.amount = 1500
        t.save()
        t.refresh_from_db()
        assert t.reference_code == orig_code

    def test_status_initial_and_change(self):
        user, w1, w2, pr = self.create_wallets_and_pr()
        t = Transaction.objects.create(from_wallet=w1, to_wallet=w2, amount=500, payment_request=pr)
        assert t.status == TransactionStatus.PENDING
        t.status = TransactionStatus.SUCCESS
        t.save()
        t.refresh_from_db()
        assert t.status == TransactionStatus.SUCCESS

    def test_str(self):
        user, w1, w2, pr = self.create_wallets_and_pr()
        t = Transaction.objects.create(from_wallet=w1, to_wallet=w2, amount=1000, payment_request=pr)
        assert "Transaction" in str(t)

    def test_missing_required_fields(self):
        user, w1, w2, pr = self.create_wallets_and_pr()
        with pytest.raises(ValidationError):
            t = Transaction(from_wallet=w1, amount=1000, payment_request=pr)
            t.full_clean()
        with pytest.raises(ValidationError):
            t = Transaction(to_wallet=w2, amount=1000, payment_request=pr)
            t.full_clean()
        with pytest.raises(ValidationError):
            t = Transaction(from_wallet=w1, to_wallet=w2, payment_request=pr)
            t.full_clean()
        with pytest.raises(ValidationError):
            t = Transaction(from_wallet=w1, to_wallet=w2, amount=-1, payment_request=pr)
            t.full_clean()

    def test_wallet_deletion_cascade(self):
        user, w1, w2, pr = self.create_wallets_and_pr()
        t = Transaction.objects.create(from_wallet=w1, to_wallet=w2, amount=1000, payment_request=pr)
        txn_id = t.id
        w1.delete()
        assert not Transaction.objects.filter(id=txn_id).exists()

    def test_duplicate_reference_code_fails(self):
        user, w1, w2, pr = self.create_wallets_and_pr()
        t1 = Transaction.objects.create(
            from_wallet=w1, to_wallet=w2, amount=1000, payment_request=pr, reference_code="DUPLICATE"
        )
        with pytest.raises(Exception):
            Transaction.objects.create(
                from_wallet=w1, to_wallet=w2, amount=1100, payment_request=pr, reference_code="DUPLICATE"
            )

    def test_transaction_payment_request_link(self):
        user, w1, w2, pr = self.create_wallets_and_pr()
        t = Transaction.objects.create(from_wallet=w1, to_wallet=w2, amount=1000, payment_request=pr)
        assert t.payment_request == pr

    def test_long_description(self):
        user, w1, w2, pr = self.create_wallets_and_pr()
        desc = "a" * 500
        t = Transaction.objects.create(from_wallet=w1, to_wallet=w2, amount=1000, payment_request=pr, description=desc)
        assert t.description == desc

    def test_on_delete_payment_request_set_null(self):
        user, w1, w2, pr = self.create_wallets_and_pr()
        t = Transaction.objects.create(from_wallet=w1, to_wallet=w2, amount=1000, payment_request=pr)
        pr.delete()
        t.refresh_from_db()
        assert t.payment_request is None

    def test_allow_null_fields(self):
        user, w1, w2, pr = self.create_wallets_and_pr()
        t = Transaction.objects.create(from_wallet=w1, to_wallet=w2, amount=1000)
        assert t.payment_request is None

    def test_save_rare_collision(self, monkeypatch):
        # simulate rare reference_code collision (optional)
        user, w1, w2, pr = self.create_wallets_and_pr()
        seen = set()
        orig_generate = Transaction.save
        def fake_save(self, *args, **kwargs):
            if not self.reference_code:
                # always set to fixed value for test
                self.reference_code = "COLLISION"
            return orig_generate(self, *args, **kwargs)
        monkeypatch.setattr(Transaction, "save", fake_save)
        t1 = Transaction(from_wallet=w1, to_wallet=w2, amount=1000, payment_request=pr)
        t1.save()
        with pytest.raises(Exception):
            t2 = Transaction(from_wallet=w1, to_wallet=w2, amount=1001, payment_request=pr)
            t2.save()

