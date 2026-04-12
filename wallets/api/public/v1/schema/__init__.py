# wallets/api/public/v1/schema/__init__.py

from .installment import installments_schema
from .installment_plan import (
    installment_plans_schema,
    plan_installments_action_schema,
)

from wallets.api.public.v1.schema.payment_requests import (
    merchant_pos_payment_cancel_schema,
    merchant_pos_payment_create_schema,
    merchant_pos_payment_list_schema,
    merchant_pos_payment_retrieve_schema,
    payment_confirm_schema,
    payment_list_schema,
    payment_retrieve_schema,
)
from .transfer import (
    transfers_list_schema,
    transfer_retrieve_schema,
    transfer_create_schema,
    transfer_confirm_schema,
    transfer_reject_schema,
)
