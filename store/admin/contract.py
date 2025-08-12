# store/admin/store_contract.py

from django.contrib import admin

from lib.cas_auth.utils import check_user_role
from lib.erp_base.admin import BaseAdmin, dynamic_cardboard_model_admin
from store.models.contract import StoreContract


@admin.register(StoreContract)
class StoreContractAdmin(
    dynamic_cardboard_model_admin(StoreContract, BaseAdmin)
):
    list_display = [
        "id",
        "store",
        "interest_rate",
        "max_credit_per_user",
        "contract_reviewer_verifier",
        "contract_reviewer_verification_time",
        "get_status",
        "active",
    ]
    list_filter = ["active", "status"]
    search_fields = ["store__name", "store__code"]


    def get_fieldsets(self, request, obj=None):
        fieldsets = ((None, {
            "fields": ("store", "get_status", "active")
        }), ("اعتبارات و بازپرداخت", {
            "fields": (
                "min_credit_per_user",
                "max_credit_per_user",
                "min_repayment_months",
                "max_repayment_months",
                "allowed_period_months",
                "interest_rate",
            )
        }),) + super().get_fieldsets(request, obj)

        if request.user.is_superuser:
            fieldsets += (("ادمین", {"fields": ("extra_document",)}),)

        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        rfs = ("get_status",)
        if request.user.is_superuser:
            return rfs
        rfs += super().get_readonly_fields(
            request, obj=obj, user_roles={
                "contract_reviewer": (
                        obj and
                        obj.status == 1 and
                        check_user_role(
                            request.user.roles, "Contract_Reviewer"
                        )
                )
            }
        )
        return rfs
