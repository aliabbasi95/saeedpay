# wallets/tests/models/test_transaction.py

import pytest

from wallets.models import Wallet, PaymentRequest, Transaction
from wallets.utils.choices import OwnerType, WalletKind, TransactionStatus


@pytest.mark.django_db
class TestTransactionModel:

    def setup_env(self, store):
        user = store.merchant.user
        buyer = user
        w_from = Wallet.objects.create(
            user=buyer, kind=WalletKind.CASH, owner_type=OwnerType.CUSTOMER
        )
        w_to = Wallet.objects.create(
            user=user, kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT
        )
        pr = PaymentRequest.objects.create(
            store=store, amount=500, return_url="https://ok.com"
        )
        return w_from, w_to, pr

    def test_reference_code_generated_and_unique(self, store):
        w_from, w_to, pr = self.setup_env(store)
        codes = set()
        for i in range(5):
            t = Transaction.objects.create(
                from_wallet=w_from, to_wallet=w_to, amount=500 + i,
                payment_request=pr
            )
            assert t.reference_code not in codes
            codes.add(t.reference_code)

    def test_manual_reference_code_not_overwritten(self, store):
        w_from, w_to, pr = self.setup_env(store)
        t = Transaction(
            from_wallet=w_from, to_wallet=w_to, amount=1000,
            payment_request=pr, reference_code="TXN12345"
        )
        t.save()
        assert t.reference_code == "TXN12345"

    def test_reference_code_persists_after_save(self, store):
        w_from, w_to, pr = self.setup_env(store)
        t = Transaction.objects.create(
            from_wallet=w_from, to_wallet=w_to, amount=1000, payment_request=pr
        )
        orig = t.reference_code
        t.amount = 1500
        t.save()
        t.refresh_from_db()
        assert t.reference_code == orig

    def test_status_initial_and_change(self, store):
        w_from, w_to, pr = self.setup_env(store)
        t = Transaction.objects.create(
            from_wallet=w_from, to_wallet=w_to, amount=500, payment_request=pr
        )
        assert t.status == TransactionStatus.PENDING
        t.status = TransactionStatus.SUCCESS
        t.save()
        t.refresh_from_db()
        assert t.status == TransactionStatus.SUCCESS

    def test_str_non_empty(self, store):
        w_from, w_to, pr = self.setup_env(store)
        t = Transaction.objects.create(
            from_wallet=w_from, to_wallet=w_to, amount=1000, payment_request=pr
        )
        assert isinstance(str(t), str)
        assert len(str(t)) > 0

    def test_on_delete_payment_request_set_null(self, store):
        w_from, w_to, pr = self.setup_env(store)
        t = Transaction.objects.create(
            from_wallet=w_from, to_wallet=w_to, amount=1000, payment_request=pr
        )
        pr.delete()
        t.refresh_from_db()
        assert t.payment_request is None

    def test_allow_null_fields(self, store):
        w_from, w_to, _ = self.setup_env(store)
        t = Transaction.objects.create(
            from_wallet=w_from, to_wallet=w_to, amount=1000
        )
        assert t.payment_request is None

    def test_duplicate_reference_code_fails(self, store):
        w_from, w_to, pr = self.setup_env(store)
        Transaction.objects.create(
            from_wallet=w_from, to_wallet=w_to, amount=1000,
            payment_request=pr, reference_code="DUPLICATE"
        )
        with pytest.raises(Exception):
            Transaction.objects.create(
                from_wallet=w_from, to_wallet=w_to, amount=1100,
                payment_request=pr, reference_code="DUPLICATE"
            )
