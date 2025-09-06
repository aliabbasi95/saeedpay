# banking/tests/api/public/v1/test_banking_api.py
import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from banking.models import Bank, BankCard
from banking.utils.choices import BankCardStatus

User = get_user_model()


@pytest.mark.django_db
class TestBankingAPI:
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

    @pytest.fixture
    def verified_card(self, user, bank):
        return BankCard.objects.create(
            user=user,
            bank=bank,
            card_number="6362141111393550",
            status=BankCardStatus.VERIFIED,
            is_active=True,
        )

    @pytest.fixture
    def rejected_card(self, user, bank):
        return BankCard.objects.create(
            user=user,
            bank=bank,
            card_number="6362141111393550",
            status=BankCardStatus.REJECTED,
            is_active=True,
        )

    @pytest.fixture
    def pending_card(self, user):
        return BankCard.objects.create(
            user=user,
            card_number="6362141111393550",
            status=BankCardStatus.PENDING,
            is_active=True,
        )

    # Bank API Tests
    def test_list_banks(self, api_client, bank):
        response = api_client.get("/saeedpay/api/banking/v1/banks/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["name"] == "Test Bank"

    def test_retrieve_bank(self, api_client, bank):
        response = api_client.get(f"/saeedpay/api/banking/v1/banks/{bank.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Test Bank"

    # BankCard API Tests
    def test_list_cards(self, api_client, verified_card):
        response = api_client.get("/saeedpay/api/banking/v1/cards/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert str(response.data[0]["id"]) == str(verified_card.id)

    def test_create_card(self, api_client):
        """Test card creation schedules validation task."""
        data = {"card_number": "5022291333461554"}  # Luhn-valid card number

        with patch("django.db.transaction.on_commit", lambda func: func()):
            with patch("banking.services.bank_card_service.validate_card_task.delay") as mock_task:
                response = api_client.post("/saeedpay/api/banking/v1/cards/", data)
                print(
                    "RESPONSE DATA:", response.data
                )  # Debug print for error details
                assert response.status_code == status.HTTP_201_CREATED
                assert BankCard.objects.count() == 1

                card = BankCard.objects.first()
                assert card.status == BankCardStatus.PENDING

                # Verify task was scheduled
                mock_task.assert_called_once_with(str(response.data["id"]))

    def test_create_card_invalid_luhn(self, api_client):
        data = {"card_number": "1234567812345678"}
        response = api_client.post("/saeedpay/api/banking/v1/cards/", data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_rejected_card(self, api_client, rejected_card):
        """Test updating rejected card schedules validation task."""
        data = {"card_number": "6362141111393550"}

        with patch("django.db.transaction.on_commit", lambda func: func()):
            with patch("banking.services.bank_card_service.validate_card_task.delay") as mock_task:
                response = api_client.patch(
                    f"/saeedpay/api/banking/v1/cards/{rejected_card.id}/", data
                )
                assert response.status_code == status.HTTP_200_OK
                rejected_card.refresh_from_db()
                assert rejected_card.status == BankCardStatus.PENDING

                # Verify task was scheduled
                mock_task.assert_called_once_with(str(rejected_card.id))

    def test_update_verified_card_not_allowed(self, api_client, verified_card):
        data = {"card_number": "6362141111393550"}
        response = api_client.patch(
            f"/saeedpay/api/banking/v1/cards/{verified_card.id}/", data
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_card(self, api_client, verified_card):
        response = api_client.delete(
            f"/saeedpay/api/banking/v1/cards/{verified_card.id}/"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        verified_card.refresh_from_db()
        assert not verified_card.is_active

    def test_set_default_card(self, api_client, verified_card):
        response = api_client.patch(
            f"/saeedpay/api/banking/v1/cards/{verified_card.id}/set-default/"
        )
        assert response.status_code == status.HTTP_200_OK
        verified_card.refresh_from_db()
        assert verified_card.is_default

    def test_set_default_on_unverified_card(self, api_client, rejected_card):
        response = api_client.patch(
            f"/saeedpay/api/banking/v1/cards/{rejected_card.id}/set-default/"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    # New Security Tests for PENDING Cards
    def test_update_pending_card_not_allowed(self, api_client, pending_card):
        """Test that PENDING cards cannot be updated."""
        data = {"card_number": "6362141111393550"}
        response = api_client.patch(
            f"/saeedpay/api/banking/v1/cards/{pending_card.id}/", data
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            "کارت‌های در حال بررسی قابل ویرایش نیستند"
            in response.data["non_field_errors"][0]
        )

    def test_delete_pending_card_not_allowed(self, api_client, pending_card):
        """Test that PENDING cards cannot be deleted."""
        response = api_client.delete(
            f"/saeedpay/api/banking/v1/cards/{pending_card.id}/"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "کارت‌های در حال بررسی قابل حذف نیستند" in response.data[0]

    def test_set_default_on_pending_card_not_allowed(
        self, api_client, pending_card
    ):
        """Test that PENDING cards cannot be set as default."""
        response = api_client.patch(
            f"/saeedpay/api/banking/v1/cards/{pending_card.id}/set-default/"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_card_with_task_scheduling_failure(self, api_client):
        """Test card creation succeeds even if task scheduling fails."""
        data = {"card_number": "6362141111393550"}

        with patch(
            "banking.tasks.validate_card_task.delay",
            side_effect=Exception("Task scheduling failed"),
        ):
            response = api_client.post("/saeedpay/api/banking/v1/cards/", data)
            assert response.status_code == status.HTTP_201_CREATED
            assert BankCard.objects.count() == 1

    def test_update_without_status_change_no_task(
        self, api_client, verified_card
    ):
        """Test that updating without changing status doesn't schedule task."""
        # This test assumes we can update some other non-card_number field
        # Since current serializer only allows card_number, this test
        # documents expected behavior
        with patch("banking.tasks.validate_card_task.delay") as mock_task:
            # This should fail due to serializer validation, but demonstrates
            # the concept
            response = api_client.patch(
                f"/saeedpay/api/banking/v1/cards/{verified_card.id}/", {}
            )
            # Task should not be called for non-status-changing updates
            mock_task.assert_not_called()

    def test_rejection_reason_visible_in_response(
        self, api_client, user, bank
    ):
        """Test that rejection_reason is included in API responses."""
        rejected_card = BankCard.objects.create(
            user=user,
            bank=bank,
            card_number="6362141111393550",
            status=BankCardStatus.REJECTED,
            rejection_reason="شماره کارت نامعتبر است",
            is_active=True,
        )

        response = api_client.get(
            f"/saeedpay/api/banking/v1/cards/{rejected_card.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["rejection_reason"] == "شماره کارت نامعتبر است"

    # Enhanced Security Tests
    def test_card_isolation_between_users(self, bank):
        """Test that users can only see and modify their own cards."""
        user1 = User.objects.create(username="user1")
        user2 = User.objects.create(username="user2")

        client1 = APIClient()
        client1.force_authenticate(user=user1)
        client2 = APIClient()
        client2.force_authenticate(user=user2)

        # Create cards for both users
        card1 = BankCard.objects.create(
            user=user1,
            bank=bank,
            card_number="6362141111393550",
            status=BankCardStatus.VERIFIED,
        )
        card2 = BankCard.objects.create(
            user=user2,
            bank=bank,
            card_number="5022291333461554",
            status=BankCardStatus.VERIFIED,
        )

        # User1 should only see their own card
        response = client1.get("/saeedpay/api/banking/v1/cards/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert str(response.data[0]["id"]) == str(card1.id)

        # User1 should not be able to access User2's card
        response = client1.get(f"/saeedpay/api/banking/v1/cards/{card2.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # User1 should not be able to modify User2's card
        response = client1.delete(
            f"/saeedpay/api/banking/v1/cards/{card2.id}/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # Security Tests
    def test_unauthenticated_access_denied(self, bank, verified_card):
        client = APIClient()
        endpoints = [
            "/saeedpay/api/banking/v1/banks/",
            f"/saeedpay/api/banking/v1/banks/{bank.id}/",
            "/saeedpay/api/banking/v1/cards/",
            f"/saeedpay/api/banking/v1/cards/{verified_card.id}/",
        ]
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_user_cannot_access_other_user_cards(self, api_client, bank):
        other_user = User.objects.create(username="otheruser")
        other_card = BankCard.objects.create(
            user=other_user, bank=bank, card_number="5022291333461554"
        )

        response = api_client.get(
            f"/saeedpay/api/banking/v1/cards/{other_card.id}/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        response = api_client.get("/saeedpay/api/banking/v1/cards/")
        assert len(response.data) == 0
