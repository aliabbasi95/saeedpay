# banking/services/bank_card_service.py

from banking.models import BankCard
from django.db import transaction


def is_luhn_valid(card_number: str) -> bool:
    """
    Validate card number using Luhn algorithm.
    """
    if not card_number.isdigit() or len(card_number) != 16:
        return False

    total = 0
    for i, digit in enumerate(card_number):
        n = int(digit)
        if (i + 1) % 2 != 0:  # Odd positions (1-indexed)
            n *= 2
            if n >= 10:
                n -= 9
        total += n

    return total % 10 == 0


def is_sheba_valid(sheba: str) -> bool:
    """
    Basic validation for Sheba format.
    """
    return sheba.startswith("IR") and len(sheba) == 26 and sheba[2:].isdigit()


def normalize_sheba(sheba: str) -> str:
    """
    Normalize Sheba by ensuring it starts with 'IR'.
    """
    if not sheba.startswith("IR"):
        return "IR" + sheba
    return sheba


def set_as_default(user, card_id):
    """
    Set a card as the default for a user, ensuring only one is default.
    """
    with transaction.atomic():
        BankCard.objects.filter(user=user, is_default=True).update(
            is_default=False
        )
        card = BankCard.objects.get(id=card_id, user=user)
        card.is_default = True
        card.save(update_fields=["is_default"])
    return card


def soft_delete_card(card):
    """
    Soft delete a card by setting is_active to False.
    """
    card.is_active = False
    card.save(update_fields=["is_active"])
    return card
