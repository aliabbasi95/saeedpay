# wallets/services/credit.py

from decimal import Decimal, ROUND_HALF_UP, getcontext


def evaluate_user_credit(requested_amount: int, contract) -> int:
    return min(requested_amount, contract.max_credit_per_user)


getcontext().prec = 28


def calculate_installments(
        amount: int,
        duration_months: int,
        period_months: int,
        annual_interest_rate: float
) -> dict:
    if period_months == 0:
        raise ValueError("پریود اقساط نمی‌تواند صفر باشد.")

    amount = Decimal(amount)
    r_annual = Decimal(annual_interest_rate) / Decimal(100)
    period_count = Decimal(duration_months) / Decimal(period_months)
    n = int(period_count.to_integral_value(rounding=ROUND_HALF_UP))

    r_periodic = r_annual / (Decimal(12) / Decimal(period_months))

    if r_periodic == 0:
        installment_amount = (amount / n).quantize(
            Decimal("1."), rounding=ROUND_HALF_UP
        )
        total_repayment = installment_amount * n
    else:
        factor = (Decimal(1) + r_periodic) ** n
        numerator = amount * r_periodic * factor
        denominator = factor - Decimal(1)
        raw_installment = numerator / denominator
        installment_amount = raw_installment.quantize(
            Decimal("1."), rounding=ROUND_HALF_UP
        )
        total_repayment = installment_amount * n

    return {
        "installment_count": n,
        "installment_amount": int(installment_amount),
        "total_repayment": int(total_repayment),
        "period_months": int(period_months),
        "interest_rate": float(annual_interest_rate),
    }
