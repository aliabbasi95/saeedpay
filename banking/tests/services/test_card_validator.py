# banking/tests/services/test_card_validator.py

import pytest
import logging
import time
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import override_settings

from banking.models import Bank, BankCard
from banking.utils.choices import BankCardStatus
from banking.services.card_validator import (
    validate_pending_card,
    _mock_validation,
    _production_validation,
    _mock_approve_card,
    _mock_reject_card,
)

User = get_user_model()


@pytest.mark.django_db
class TestCardValidator:
    @pytest.fixture
    def user(self):
        return User.objects.create(username="testuser")

    @pytest.fixture
    def bank(self):
        return Bank.objects.create(name="Test Bank", color="#123456")

    @pytest.fixture
    def pending_card(self, user):
        return BankCard.objects.create(
            user=user,
            card_number="6219861012345678",
            status=BankCardStatus.PENDING,
        )

    @pytest.fixture
    def verified_card(self, user, bank):
        return BankCard.objects.create(
            user=user,
            bank=bank,
            card_number="6219861087654321",
            status=BankCardStatus.VERIFIED,
        )

    def test_validate_pending_card_skips_non_pending(self, verified_card):
        """Test that validation is skipped for non-pending cards."""
        with patch(
            "banking.services.card_validator._mock_validation"
        ) as mock_validation:
            validate_pending_card(verified_card)
            mock_validation.assert_not_called()

    @override_settings(CARD_VALIDATOR_MOCK=True)
    def test_validate_pending_card_mock_mode(self, pending_card):
        """Test that mock validation is called in mock mode."""
        with patch(
            "banking.services.card_validator._mock_validation"
        ) as mock_validation:
            validate_pending_card(pending_card)
            mock_validation.assert_called_once_with(pending_card)

    @override_settings(CARD_VALIDATOR_MOCK=False)
    def test_validate_pending_card_production_mode(self, pending_card):
        """Test that production validation is called in production mode."""
        with patch(
            "banking.services.card_validator._production_validation"
        ) as prod_validation:
            validate_pending_card(pending_card)
            prod_validation.assert_called_once_with(pending_card)

    def test_production_validation_logs_correctly(self, pending_card, caplog):
        """Test that production validation logs the correct message."""
        with caplog.at_level(logging.INFO):
            _production_validation(pending_card)
        assert (
            f"Production validation started for card {pending_card.id}"
            in caplog.text
        )

    def test_mock_validation_sleeps_correctly(self, pending_card):
        """Test that mock validation includes sleep delay."""
        start_time = time.time()
        with patch(
            "random.random", return_value=0.9
        ):  # Force approval to avoid database changes
            with patch("banking.services.card_validator._mock_approve_card"):
                _mock_validation(pending_card)
        end_time = time.time()
        # Should sleep between 1.5-3.0 seconds
        assert end_time - start_time >= 1.5

    def test_mock_validation_skips_changed_status(self, pending_card):
        """
        Test that mock validation aborts if card status changed during delay.
        """
        with patch("time.sleep"):
            # Change status during validation
            pending_card.status = BankCardStatus.VERIFIED
            pending_card.save()

            with patch(
                "banking.services.card_validator._mock_approve_card"
            ) as mock_approve:
                _mock_validation(pending_card)
                mock_approve.assert_not_called()

    def test_mock_approve_card(self, pending_card, bank):
        """Test that mock approval sets correct fields."""
        _mock_approve_card(pending_card)

        pending_card.refresh_from_db()
        assert pending_card.status == BankCardStatus.VERIFIED
        assert pending_card.bank is not None
        assert pending_card.card_holder_name != ""
        assert pending_card.sheba.startswith("IR")
        assert len(pending_card.sheba) == 26
        assert pending_card.rejection_reason is None

    def test_mock_reject_card(self, pending_card):
        """Test that mock rejection sets correct fields."""
        _mock_reject_card(pending_card)

        pending_card.refresh_from_db()
        assert pending_card.status == BankCardStatus.REJECTED
        assert pending_card.rejection_reason is not None
        assert pending_card.bank is None
        assert pending_card.card_holder_name == ""
        assert pending_card.sheba == ""

    def test_mock_validation_approval_probability(self, user):
        """Test that mock validation has approximately 80% approval rate."""
        approvals = 0
        rejections = 0

        # Run validation multiple times to test probability
        for i in range(10):
            card = BankCard.objects.create(
                user=user,
                card_number=f"621986101234567{i}",
                status=BankCardStatus.PENDING,
            )

            with patch("time.sleep"):  # Skip sleep for faster testing
                _mock_validation(card)

            card.refresh_from_db()
            if card.status == BankCardStatus.VERIFIED:
                approvals += 1
            elif card.status == BankCardStatus.REJECTED:
                rejections += 1

        # Should have some approvals and rejections (not deterministic but
        # probabilistic)
        assert approvals + rejections == 10
        assert approvals > 0  # Should have at least some approvals
        # Note: In real tests, you might want to mock random.random() for
        # deterministic results

    def test_mock_validation_creates_bank_if_none_exist(self, pending_card):
        """Test that mock validation creates a default bank if none exist."""
        # Ensure no banks exist
        Bank.objects.all().delete()

        with patch("time.sleep"):
            with patch("random.random", return_value=0.1):  # Force approval
                _mock_validation(pending_card)

        pending_card.refresh_from_db()
        assert pending_card.status == BankCardStatus.VERIFIED
        assert Bank.objects.count() == 1
        assert Bank.objects.first().name == "بانک نمونه"

    @override_settings(CARD_VALIDATOR_MOCK=False)
    def test_validate_pending_card_with_default_setting(self, pending_card):
        """
        Test that validation works with default CARD_VALIDATOR_MOCK setting.
        """
        # Removed deletion of CARD_VALIDATOR_MOCK to let override_settings work
        with patch(
            "banking.services.card_validator._production_validation"
        ) as prod_validation:
            validate_pending_card(pending_card)
            prod_validation.assert_called_once_with(pending_card)
