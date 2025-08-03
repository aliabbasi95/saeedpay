# wallets/services/installment.py

from wallets.models import Transaction, Installment
from wallets.utils.choices import InstallmentStatus


def pay_installment(
        installment: Installment,
        amount: int,
        transaction: Transaction,
        penalty_rate: float = 0.005
):
    if installment.status == InstallmentStatus.PAID:
        raise Exception("این قسط قبلاً پرداخت شده است.")

    penalty = installment.calculate_penalty(daily_rate=penalty_rate)
    total_due = installment.amount + penalty

    if amount < total_due:
        raise Exception("مبلغ پرداخت‌شده کمتر از مجموع قسط و جریمه است.")

    installment.mark_paid(
        amount_paid=installment.amount,
        penalty_paid=penalty,
        transaction=transaction
    )
