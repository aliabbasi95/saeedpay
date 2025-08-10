from django.db import transaction
from django.utils import timezone

from wallets.models import InstallmentPlan, InstallmentRequest
from wallets.services import generate_installments_for_plan
from wallets.utils.choices import (
    InstallmentRequestStatus,
    InstallmentSourceType,
)


@transaction.atomic
def finalize_installment_request(request: InstallmentRequest):
    existing_plan = InstallmentPlan.objects.filter(
        source_type=InstallmentSourceType.BNPL,
        source_object_id=request.id
    ).first()

    if existing_plan:
        return existing_plan

    plan = InstallmentPlan.objects.create(
        user=request.customer.user,
        source_type="bnpl",
        source_object_id=request.id,
        total_amount=request.system_approved_amount,
        duration_months=request.duration_months,
        period_months=request.period_months,
        interest_rate=request.contract.interest_rate,
        description=f"Plan for BNPL request #{request.id}",
        created_by="merchant"
    )

    generate_installments_for_plan(plan)

    request.status = InstallmentRequestStatus.COMPLETED
    request.merchant_confirmed_at = timezone.localtime(timezone.now())
    request.save()

    return plan
