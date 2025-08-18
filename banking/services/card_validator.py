# banking/services/card_validator.py

import logging
import random
import time

from django.apps import apps
from django.conf import settings
from django.db import transaction
from faker import Faker

from banking.utils.choices import BankCardStatus

logger = logging.getLogger(__name__)
fake = Faker("fa_IR")


def validate_pending_card(card_id: str) -> None:
    BankCard = apps.get_model("banking", "BankCard")
    try:
        card = BankCard.objects.get(id=card_id)
    except BankCard.DoesNotExist:
        logger.warning("Card %s not found, skipping validation", card_id)
        return
    # Guard clause - ensure idempotency
    if card.status != BankCardStatus.PENDING:
        logger.info(f"Card {card.id} is not pending, skipping validation")
        return

    mock_mode = getattr(settings, "CARD_VALIDATOR_MOCK", True)

    if mock_mode:
        _mock_validation(card_id)
    else:
        _production_validation(card_id)


def _production_validation(card_id: str) -> None:

    logger.info("Production validation started for card %s", card_id)
    # TODO: Implement actual validation logic
    # This would typically involve:
    # 1. Making API calls to bank services
    # 2. Validating card details
    # 3. Fetching card holder information
    # 4. Updating card status based on results


def _mock_validation(card_id: str) -> None:
    BankCard = apps.get_model("banking", "BankCard")
    # Simulate network latency
    time.sleep(random.uniform(1.5, 3.0))

    # Random outcome: 80% success, 20% rejection
    is_verified = random.random() < 0.8

    with transaction.atomic():
        card = BankCard.objects.select_for_update().get(id=card_id)
        # Refresh the card from database to avoid stale data
        card.refresh_from_db()

        # Double-check status in case it changed during the delay
        if card.status != BankCardStatus.PENDING:
            logger.info(
                f"Card {card.id} status changed during validation, aborting"
            )
            return

        if is_verified:
            _mock_approve_card(card.id)
        else:
            _mock_reject_card(card.id)


def _mock_approve_card(card_id: str) -> None:
    BankCard = apps.get_model("banking", "BankCard")
    Bank = apps.get_model("banking", "Bank")
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
    BankCard.objects.filter(id=card_id).update(
        status=BankCardStatus.VERIFIED,
        bank=bank,
        card_holder_name=card_holder_name,
        sheba=sheba,
        rejection_reason=None,
    )
    logger.info(
        f"Card {card_id} approved - Bank: {bank.name}, "
        f"Holder: {card_holder_name}, SHEBA: {sheba}"
    )


def _mock_reject_card(card_id: str) -> None:
    BankCard = apps.get_model("banking", "BankCard")
    rejection_reasons = [
        "شماره کارت نامعتبر است",
        "کارت منقضی شده است",
        "اطلاعات کارت با بانک مطابقت ندارد",
        "کارت مسدود شده است",
        "حساب مرتبط با کارت فعال نیست",
        "کارت برای تراکنش‌های آنلاین فعال نشده است",
    ]

    reason = random.choice(rejection_reasons)

    BankCard.objects.filter(id=card_id).update(
        status=BankCardStatus.REJECTED,
        rejection_reason=reason,
        bank=None,
        card_holder_name="",
        sheba="",
    )

    logger.info(f"Card {card_id} rejected - Reason: {reason}")
