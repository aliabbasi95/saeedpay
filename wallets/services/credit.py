# wallets/services/credit.py
from math import ceil


def evaluate_user_credit(requested_amount: int, contract) -> int:
    return min(requested_amount, contract.max_credit_per_user)


def calculate_installments(
        amount, duration_months, period_months, annual_interest_rate
):

    if period_months == 0:
        raise ValueError("پریود اقساط نمی‌تواند صفر باشد.")

    n = ceil(duration_months / period_months)

    r_annual = annual_interest_rate / 100
    r_periodic = r_annual / (12 / period_months)

    if r_periodic == 0:
        installment_amount = ceil(amount / n)
        total_repayment = installment_amount * n
    else:
        factor = (1 + r_periodic) ** n
        installment_amount = ceil(amount * r_periodic * factor / (factor - 1))
        total_repayment = installment_amount * n

    return {
        "installment_count": n,
        "installment_amount": installment_amount,
        "total_repayment": total_repayment,
        "period_months": period_months,
        "interest_rate": annual_interest_rate
    }