# banking/services/card_validator.py

import logging
import random
import time

from django.conf import settings
from django.db import transaction
from faker import Faker

from banking.models import BankCard, Bank
from banking.utils.choices import BankCardStatus

logger = logging.getLogger(__name__)
fake = Faker("fa_IR")


def validate_pending_card(card: BankCard) -> None:
    """
    Entry-point invoked every time a card is created or edited and
    its status becomes 'در حال بررسی'.

    Args:
        card: The BankCard instance to validate
    """
    # Guard clause - ensure idempotency
    if card.status != BankCardStatus.PENDING:
        logger.info(f"Card {card.id} is not pending, skipping validation")
        return

    mock_mode = getattr(settings, "CARD_VALIDATOR_MOCK", False)

    if mock_mode:
        _mock_validation(card)
    else:
        _production_validation(card)


def _production_validation(card: BankCard) -> None:
    """
    Production validation branch - currently a stub.

    Args:
        card: The BankCard instance to validate
    """
    logger.info(f"Production validation started for card {card.id}")
    # TODO: Implement actual validation logic
    # This would typically involve:
    # 1. Making API calls to bank services
    # 2. Validating card details
    # 3. Fetching card holder information
    # 4. Updating card status based on results


def _mock_validation(card: BankCard) -> None:
    """
    Mock validation branch with simulated network latency and random outcomes.

    Args:
        card: The BankCard instance to validate
    """
    logger.info(f"Mock validation started for card {card.id}")

    # Simulate network latency
    time.sleep(random.uniform(1.5, 3.0))

    # Random outcome: 80% success, 20% rejection
    is_verified = random.random() < 0.8

    with transaction.atomic():
        # Refresh the card from database to avoid stale data
        card.refresh_from_db()

        # Double-check status in case it changed during the delay
        if card.status != BankCardStatus.PENDING:
            logger.info(
                f"Card {card.id} status changed during validation, aborting"
            )
            return

        if is_verified:
            _mock_approve_card(card)
        else:
            _mock_reject_card(card)


def _mock_approve_card(card: BankCard) -> None:
    """
    Mock approval of a card with generated data.

    Args:
        card: The BankCard instance to approve
    """
    # Pick a random bank
    banks = list(Bank.objects.all())
    if not banks:
        logger.warning(
            "No banks available in database, creating a default one"
        )
        bank = Bank.objects.create(name="بانک نمونه", color="#1976D2")
    else:
        bank = random.choice(banks)

    # Generate plausible Persian card holder name
    card_holder_name = f"{fake.first_name()} {fake.last_name()}"

    # Generate plausible SHEBA (IR + 24 digits)
    sheba = f"IR{''.join([str(random.randint(0, 9)) for _ in range(24)])}"

    # Update card
    card.status = BankCardStatus.VERIFIED
    card.bank = bank
    card.card_holder_name = card_holder_name
    card.sheba = sheba
    card.rejection_reason = None  # Clear any previous rejection reason
    card.save(
        update_fields=[
            "status",
            "bank",
            "card_holder_name",
            "sheba",
            "rejection_reason",
        ]
    )

    logger.info(
        f"Card {card.id} approved - Bank: {bank.name}, "
        f"Holder: {card_holder_name}, SHEBA: {sheba}"
    )


def _mock_reject_card(card: BankCard) -> None:
    """
    Mock rejection of a card with a random Persian reason.

    Args:
        card: The BankCard instance to reject
    """
    rejection_reasons = [
        "شماره کارت نامعتبر است",
        "کارت منقضی شده است",
        "اطلاعات کارت با بانک مطابقت ندارد",
        "کارت مسدود شده است",
        "حساب مرتبط با کارت فعال نیست",
        "کارت برای تراکنش‌های آنلاین فعال نشده است",
    ]

    rejection_reason = random.choice(rejection_reasons)

    # Update card
    card.status = BankCardStatus.REJECTED
    card.rejection_reason = rejection_reason
    card.bank = None
    card.card_holder_name = ""
    card.sheba = ""
    card.save(
        update_fields=[
            "status",
            "rejection_reason",
            "bank",
            "card_holder_name",
            "sheba",
        ]
    )

    logger.info(f"Card {card.id} rejected - Reason: {rejection_reason}")
