# banking/tests/test_integration.py

import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient


from banking.models import Bank, BankCard
from banking.utils.choices import BankCardStatus
from banking.tasks import validate_card_task, CardValidationTask

User = get_user_model()


@pytest.mark.django_db
class TestCardValidationIntegration:
    """Integration tests for the complete card validation flow."""

    @pytest.fixture
    def user(self):
        return User.objects.create(username="testuser")

    @pytest.fixture
    def api_client(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    @pytest.fixture
    def bank(self):
        return Bank.objects.create(name="Test Bank", color="#123456")

    def test_complete_card_creation_and_validation_flow(
        self, api_client, bank
    ):
        """
        Test the complete flow from card creation to validation completion.
        """
        # Step 1: Create a card via API
        data = {"card_number": "6362141111393550"}

        with patch("banking.tasks.validate_card_task.delay") as mock_task_delay, \
     patch("banking.services.bank_card_service.enqueue_validation_if_pending", side_effect=lambda old_status, card: validate_card_task.delay(str(card.id))):
            response = api_client.post("/saeedpay/api/banking/v1/cards/", data)
            assert response.status_code == 201

            # Verify card was created in PENDING status
            card = BankCard.objects.get(card_number="6362141111393550")
            assert card.status == BankCardStatus.PENDING
            assert card.bank is None
            assert card.card_holder_name == ""

            # Verify task was scheduled
            mock_task_delay.assert_called_once_with(str(card.id))

        # Step 2: Simulate task execution (mock validation - approval)
        with override_settings(CARD_VALIDATOR_MOCK=True):
            with patch("time.sleep"):  # Skip sleep for faster testing
                with patch(
                    "random.random", return_value=0.1
                ):  # Force approval
                    result = validate_card_task(str(card.id))
                    assert result is True

        # Step 3: Verify card was approved
        card.refresh_from_db()
        assert card.status == BankCardStatus.VERIFIED
        assert card.bank is not None
        assert card.card_holder_name != ""
        assert card.sheba.startswith("IR")
        assert card.rejection_reason is None

        # Step 4: Verify card can now be set as default
        response = api_client.patch(
            f"/saeedpay/api/banking/v1/cards/{card.id}/set-default/"
        )
        assert response.status_code == 200
        card.refresh_from_db()
        assert card.is_default

    def test_complete_card_rejection_flow(self, api_client):
        """Test the complete flow for card rejection."""
        # Step 1: Create a card
        data = {"card_number": "6362141111393550"}

        with patch("banking.tasks.validate_card_task.delay"):
            response = api_client.post("/saeedpay/api/banking/v1/cards/", data)
            card = BankCard.objects.get(card_number="6362141111393550")

        # Step 2: Simulate task execution (mock validation - rejection)
        with override_settings(CARD_VALIDATOR_MOCK=True):
            with patch("time.sleep"):
                with patch(
                    "random.random", return_value=0.9
                ):  # Force rejection
                    validate_card_task(str(card.id))

        # Step 3: Verify card was rejected
        card.refresh_from_db()
        assert card.status == BankCardStatus.REJECTED
        assert card.rejection_reason is not None
        assert card.bank is None
        assert card.card_holder_name == ""

        # Step 4: Verify rejected card can be updated
        data = {"card_number": "6362141111393154"}
        with patch("banking.tasks.validate_card_task.delay") as mock_task, \
     patch("banking.services.bank_card_service.enqueue_validation_if_pending", side_effect=lambda old_status, card: validate_card_task.delay(str(card.id))):
            response = api_client.patch(
                f"/saeedpay/api/banking/v1/cards/{card.id}/", data
            )
            assert response.status_code == 200

            card.refresh_from_db()
            assert card.status == BankCardStatus.PENDING
            assert card.card_number == "6362141111393154"

            # Task should be scheduled again for re-validation
            mock_task.assert_called_once_with(str(card.id))

    def test_pending_card_restrictions(self, api_client):
        """Test that PENDING cards have proper restrictions."""
        # Create a card
        data = {"card_number": "6362141111393550"}
        with patch("banking.tasks.validate_card_task.delay"):
            response = api_client.post("/saeedpay/api/banking/v1/cards/", data)
            card = BankCard.objects.get(card_number="6362141111393550")

        # Verify PENDING card restrictions
        card_id = card.id

        # Cannot update
        response = api_client.patch(
            f"/saeedpay/api/banking/v1/cards/{card_id}/",
            {"card_number": "6362141111393154"},
        )
        assert response.status_code == 400

        # Cannot delete
        response = api_client.delete(
            f"/saeedpay/api/banking/v1/cards/{card_id}/"
        )
        assert response.status_code == 400

        # Cannot set as default
        response = api_client.patch(
            f"/saeedpay/api/banking/v1/cards/{card_id}/set-default/"
        )
        assert response.status_code == 403

    def test_task_retry_and_failure_handling(self, api_client):
        """Test task retry mechanism and failure handling."""
        # Create a card
        data = {"card_number": "6362141111393550"}
        with patch("banking.tasks.validate_card_task.delay"):
            response = api_client.post("/saeedpay/api/banking/v1/cards/", data)
            card = BankCard.objects.get(card_number="6362141111393550")

        # Simulate a task failure
        exc = Exception("Validation service unavailable")

        # We need a mock task instance to pass to on_failure
        mock_task_instance = MagicMock()
        mock_task_instance.request.retries = 3
        mock_task_instance.max_retries = 3

        # Call the on_failure handler directly to simulate permanent failure
        CardValidationTask().on_failure(
            exc, card.id, (str(card.id),), {}, None
        )

        # Verify card was marked as rejected due to system failure
        card.refresh_from_db()
        assert card.status == BankCardStatus.REJECTED
        assert "خطا در سیستم تایید کارت" in card.rejection_reason

        # Verify rejected card can still be updated to retry validation
        data = {"card_number": "6362141111393154"}
        with patch("banking.tasks.validate_card_task.delay") as mock_task, \
     patch("banking.services.bank_card_service.enqueue_validation_if_pending", side_effect=lambda old_status, card: validate_card_task.delay(str(card.id))):
            response = api_client.patch(
                f"/saeedpay/api/banking/v1/cards/{card.id}/", data
            )
            assert response.status_code == 200
            mock_task.assert_called_once()

    @override_settings(CARD_VALIDATOR_MOCK=False)
    def test_production_mode_validation(self, api_client):
        """Test that production mode validation is properly triggered."""
        data = {"card_number": "6362141111393550"}

        with patch("banking.tasks.validate_card_task.delay"):
            response = api_client.post("/saeedpay/api/banking/v1/cards/", data)
            card = BankCard.objects.get(card_number="6362141111393550")

        # Test production validation is called
        with patch(
            "banking.services.card_validator._production_validation"
        ) as mock_prod:
            validate_card_task(str(card.id))
            mock_prod.assert_called_once_with(str(card.id))

    def test_concurrent_card_operations(self, api_client, bank):
        """Test handling of concurrent operations on the same card."""
        # Create a card
        data = {"card_number": "6362141111393550"}
        with patch("banking.tasks.validate_card_task.delay"):
            response = api_client.post("/saeedpay/api/banking/v1/cards/", data)
            card = BankCard.objects.get(card_number="6362141111393550")

        # Simulate concurrent status change during validation
        def change_status_during_validation(card_instance):
            # Another process approves the card
            card_instance.status = BankCardStatus.VERIFIED
            card_instance.bank = bank
            card_instance.save()

        with patch(
            "banking.services.card_validator.validate_pending_card",
            side_effect=lambda card_id: change_status_during_validation(BankCard.objects.get(id=card_id)),
        ):
            result = validate_card_task(str(card.id))
            assert (
                result is True
            )  # Should handle concurrent changes gracefully

    def test_multiple_users_card_isolation(self):
        """Test that multiple users' cards are properly isolated."""
        user1 = User.objects.create(username="user1")
        user2 = User.objects.create(username="user2")

        client1 = APIClient()
        client1.force_authenticate(user=user1)
        client2 = APIClient()
        client2.force_authenticate(user=user2)

        # Both users create cards
        with patch("banking.tasks.validate_card_task.delay"):
            response1 = client1.post(
                "/saeedpay/api/banking/v1/cards/",
                {"card_number": "6362141111393550"},
            )
            response2 = client2.post(
                "/saeedpay/api/banking/v1/cards/",
                {"card_number": "6362141111393154"},
            )

            assert response1.status_code == 201
            assert response2.status_code == 201

        # Each user should only see their own cards
        response1 = client1.get("/saeedpay/api/banking/v1/cards/")
        response2 = client2.get("/saeedpay/api/banking/v1/cards/")

        assert len(response1.data) == 1
        assert len(response2.data) == 1
        assert response1.data[0]["last4"] == "3550"
        assert response2.data[0]["last4"] == "3154"
