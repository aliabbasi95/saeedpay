# banking/tests/test_tasks.py

import pytest
import logging
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from celery.exceptions import Retry

from banking.models import Bank, BankCard
from banking.utils.choices import BankCardStatus
from banking.tasks import (
    validate_card_task,
    CardValidationTask,
    _validate_card_task_logic,
)

User = get_user_model()


@pytest.mark.django_db
class TestCardValidationTask:
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
            card_number="6362141111393550",
            status=BankCardStatus.PENDING,
        )

    @pytest.fixture
    def verified_card(self, user, bank):
        return BankCard.objects.create(
            user=user,
            bank=bank,
            card_number="5022291333461554",
            status=BankCardStatus.VERIFIED,
        )

    def test_validate_card_task_success(self, pending_card):
        """Test successful card validation task."""
        with patch("banking.tasks.validate_pending_card") as mock_validator:
            result = validate_card_task.apply(args=[str(pending_card.id)])
            assert result.successful() is True
            mock_validator.assert_called_once_with(str(pending_card.id))

    def test_validate_card_task_card_not_found(self):
        """Test task behavior when card doesn't exist."""
        fake_id = 999999  # Use a non-existent integer id
        result = validate_card_task.apply(args=[str(fake_id)])
        assert result.get() is False

    def test_validate_card_task_skips_non_pending(self, verified_card):
        """Test task skips validation for non-pending cards."""
        with patch("banking.tasks.validate_pending_card") as mock_validator:
            result = validate_card_task.apply(args=[str(verified_card.id)])
            assert result.get() is True
            mock_validator.assert_not_called()

    def test_validate_card_task_retry_on_exception(self, pending_card):
        """Test task retry mechanism on validation failure."""
        with patch(
            "banking.tasks.validate_pending_card",
            side_effect=Exception("Validation failed"),
        ):
            with patch(
                "banking.tasks.validate_card_task.retry", side_effect=Retry
            ) as mock_retry:
                with pytest.raises(Retry):
                    validate_card_task.apply(
                        args=[str(pending_card.id)], throw=True
                    )
                mock_retry.assert_called_once()

    def test_on_failure_marks_card_as_rejected(self, pending_card):
        """Test that the on_failure handler marks the card as rejected."""
        exc = Exception("Final failure")
        task_id = "some-task-id"
        args = (str(pending_card.id),)

        CardValidationTask().on_failure(exc, task_id, args, {}, None)

        pending_card.refresh_from_db()
        assert pending_card.status == BankCardStatus.REJECTED
        assert "خطا در سیستم تایید کارت" in pending_card.rejection_reason

    def test_on_failure_handles_db_error_gracefully(self, pending_card):
        """Test that on_failure handler does not crash on DB error."""
        exc = Exception("Final failure")
        task_id = "some-task-id"
        args = (str(pending_card.id),)

        with patch(
            "banking.tasks.transaction.atomic",
            side_effect=Exception("DB Error"),
        ):
            CardValidationTask().on_failure(exc, task_id, args, {}, None)

        pending_card.refresh_from_db()
        assert pending_card.status == BankCardStatus.PENDING

    def test_validate_card_task_exponential_backoff(self, pending_card):
        """Test that retry uses exponential backoff."""
        mock_task_self = MagicMock()
        mock_task_self.request.retries = 1
        mock_task_self.max_retries = 3
        mock_task_self.retry.side_effect = Retry

        with patch(
            "banking.tasks.validate_pending_card",
            side_effect=Exception("Validation failed"),
        ):
            with pytest.raises(Retry):
                _validate_card_task_logic(mock_task_self, str(pending_card.id))

        mock_task_self.retry.assert_called_once()
        assert mock_task_self.retry.call_args.kwargs["countdown"] == 120

    def test_validate_card_task_logging(self, pending_card, caplog):
        """Test that task logs appropriate messages."""
        with patch("banking.tasks.validate_pending_card"):
            with caplog.at_level(logging.INFO):
                validate_card_task.apply(args=[str(pending_card.id)])

            assert (
                f"Card validation logic completed successfully for card "
                f"{pending_card.id}" in caplog.text
            )

    def test_validate_card_task_concurrent_status_change(self, pending_card):
        """
        Test behavior when card status changes between task start and
        validation.
        """

        def change_status_during_validation(*args, **kwargs):
            card = BankCard.objects.get(id=pending_card.id)
            card.status = BankCardStatus.VERIFIED
            card.save()
            return True

        with patch(
            "banking.tasks.validate_pending_card",
            side_effect=change_status_during_validation,
        ):
            result = validate_card_task.apply(args=[str(pending_card.id)])
            assert result.get() is True
