from datetime import timezone

from wallets.models import InstallmentPlan, InstallmentRequest
from wallets.services import generate_installments_for_plan


def finalize_installment_request(request: InstallmentRequest):
    plan = InstallmentPlan.objects.create(
        user=request.customer.user,
        source_type="bnpl",
        source_object_id=request.id,
        total_amount=request.approved_amount,
        duration_months=request.duration_months,
        period_months=request.period_months,
        interest_rate=request.contract.interest_rate,
        description=f"Plan for BNPL request #{request.id}",
        created_by="merchant"
    )

    generate_installments_for_plan(plan)

    request.status = "completed"
    request.merchant_confirmed_at = timezone.now()
    request.save()

    return plan
