# banking/tests/models/test_banking_models.py
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from banking.models import Bank, BankCard
from banking.utils.choices import BankCardStatus

User = get_user_model()


@pytest.mark.django_db
class TestBankModel:
    def test_create_bank(self):
        bank = Bank.objects.create(name="Test Bank", color="#123456")
        assert str(bank) == "Test Bank"
        assert Bank.objects.count() == 1


@pytest.mark.django_db
class TestBankCardModel:
    @pytest.fixture
    def user(self):
        return User.objects.create(username="testuser")

    @pytest.fixture
    def bank(self):
        return Bank.objects.create(name="Test Bank", color="#FFFFFF")

    def test_create_bank_card(self, user, bank):
        card = BankCard.objects.create(
            user=user,
            bank=bank,
            card_number="1234567812345670",
            card_holder_name="Test User",
            status=BankCardStatus.PENDING,
        )
        assert str(card) == f"{user}'s card - 5670"
        assert BankCard.objects.count() == 1

    def test_default_card_uniqueness(self, user, bank):
        card1 = BankCard.objects.create(
            user=user,
            bank=bank,
            card_number="6362141111393550",
            is_default=True,
            status=BankCardStatus.VERIFIED,
        )
        card2 = BankCard.objects.create(
            user=user,
            bank=bank,
            card_number="6362141111393551",
            is_default=True,
            status=BankCardStatus.VERIFIED,
        )
        card1.refresh_from_db()
        card2.refresh_from_db()
        assert card1.is_default is False
        assert card2.is_default is True
        assert BankCard.objects.filter(user=user, is_default=True).count() == 1

    def test_is_default_only_for_verified_cards(self, user, bank):
        with pytest.raises(ValidationError):
            BankCard.objects.create(
                user=user,
                bank=bank,
                card_number="1234567812345670",
                is_default=True,
                status=BankCardStatus.PENDING,
            )

    def test_card_number_update_resets_fields(self, user, bank):
        card = BankCard.objects.create(
            user=user,
            bank=bank,
            card_number="1234567812345670",
            card_holder_name="Test User",
            status=BankCardStatus.REJECTED,
            sheba="IR123456789012345678901234",
            rejection_reason="Previous rejection reason",
        )
        card.card_number = "9876543210987654"
        card.save()

        updated_card = BankCard.objects.get(id=card.id)
        assert updated_card.status == BankCardStatus.PENDING
        assert updated_card.bank is None
        assert updated_card.card_holder_name == ""
        assert not updated_card.is_default
        assert updated_card.sheba == ""
        # rejection_reason should remain as it might be useful for history

    def test_rejection_reason_field(self, user):
        """Test that rejection_reason field works correctly."""
        card = BankCard.objects.create(
            user=user,
            card_number="1234567812345670",
            status=BankCardStatus.REJECTED,
            rejection_reason="شماره کارت نامعتبر است",
        )
        assert card.rejection_reason == "شماره کارت نامعتبر است"

        # Test that rejection_reason can be null
        card.rejection_reason = None
        card.save()
        card.refresh_from_db()
        assert card.rejection_reason is None
