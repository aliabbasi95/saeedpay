# banking/api/public/v1/schema/__init__.py

from .schema_bank import bank_viewset_schema
from .schema_bank_card import (
    bank_card_viewset_schema,
    set_default_action_schema,
)
