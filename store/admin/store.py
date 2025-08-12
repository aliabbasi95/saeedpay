# store/admin/store.py

from django.contrib import admin

from lib.cas_auth.utils import check_user_role
from lib.erp_base.admin import BaseAdmin, dynamic_cardboard_model_admin
from store.models import Store


@admin.register(Store)
class StoreAdmin(dynamic_cardboard_model_admin(Store, BaseAdmin)):
    list_display = [
        "id",
        "name",
        "code",
        "merchant",
        "is_active",
        "get_status",
        "store_reviewer_verifier",
        "jalali_verification_time",
    ]
    list_filter = ["is_active"]
    search_fields = ["name", "id"]

    def get_fieldsets(self, request, obj=None):
        fieldsets = ((None, {
            "fields": (
                "merchant",
                "get_status",
            )
        }), ("اطلاعات", {
            "fields": (
                "name",
                "code",
                "address",
                "is_active",
            )
        }),) + super(StoreAdmin, self).get_fieldsets(
            request, obj
        )
        if request.user.is_superuser:
            fieldsets += (("ادمین", {"fields": ("extra_document",)}),)
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        rfs = ("get_status",)
        if request.user.is_superuser:
            return rfs
        rfs += super(StoreAdmin, self).get_readonly_fields(
            request, obj=obj, user_roles={
                "store_reviewer": (
                        obj and
                        obj.status == 1 and
                        check_user_role(request.user.roles, "Store_Reviewer")
                ),
            }
        )
        return rfs
