# banking/services/bank_card_service.py

from django.db import transaction

from banking.utils.choices import BankCardStatus
from banking.tasks import validate_card_task


def normalize_card_number(number: str) -> str:
    return "".join(ch for ch in number if ch.isdigit())

def enqueue_validation_if_pending(old_status, card):
    if card.status == BankCardStatus.PENDING and old_status != BankCardStatus.PENDING:
        transaction.on_commit(lambda: validate_card_task.delay(str(card.id)))

def is_luhn_valid(card_number: str) -> bool:
    card_number = normalize_card_number(card_number)
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
    return sheba.startswith("IR") and len(sheba) == 26 and sheba[2:].isdigit()


def normalize_sheba(sheba: str) -> str:
    sheba = (sheba or "").replace(" ", "").upper()
    if not sheba.startswith("IR"):
        return "IR" + sheba
    return sheba


def set_as_default(user, card_id):
    from banking.models import BankCard
    with transaction.atomic():
        BankCard.objects.filter(user=user, is_default=True).update(
            is_default=False
        )
        card = BankCard.objects.get(id=card_id, user=user)
        card.is_default = True
        card.save(update_fields=["is_default"])
    return card


def soft_delete_card(card):
    updates = ["is_active"]
    card.is_active = False
    if card.is_default:
        card.is_default = False
        updates.append("is_default")
    card.save(update_fields=updates)
    return card
