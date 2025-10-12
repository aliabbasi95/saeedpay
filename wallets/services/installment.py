# wallets/services/installment.py

from dateutil.relativedelta import relativedelta
from django.utils import timezone

from wallets.models import Transaction, Installment, InstallmentPlan
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


def generate_installments_for_plan(plan: InstallmentPlan) -> list[Installment]:
    installments = []

    total_months = plan.duration_months
    period_months = plan.period_months
    total_amount = plan.total_amount

    count = total_months // period_months
    base_amount = total_amount // count
    remaining = total_amount - (base_amount * count)

    start_date = timezone.localtime(timezone.now()).date()

    for i in range(count):
        due_date = start_date + relativedelta(months=period_months * i)
        amount = base_amount + (remaining if i == count - 1 else 0)

        installment = Installment.objects.create(
            plan=plan,
            amount=amount,
            due_date=due_date,
            status=InstallmentStatus.UNPAID,
        )
        installments.append(installment)

    return installments
