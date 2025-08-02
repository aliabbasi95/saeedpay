# wallets/services/credit.py
from math import ceil


def evaluate_user_credit(requested_amount: int, contract) -> int:
    return min(requested_amount, contract.max_credit_per_user)


def calculate_installments(
        amount: int, duration_months: int, period_months: int
):
    if period_months == 0:
        raise ValueError("پریود اقساط نمی‌تواند صفر باشد.")

    num_installments = ceil(duration_months / period_months)
    installment_amount = ceil(amount / num_installments)
    total_repayment = installment_amount * num_installments

    return {
        "installment_count": num_installments,
        "installment_amount": installment_amount,
        "total_repayment": total_repayment,
    }
