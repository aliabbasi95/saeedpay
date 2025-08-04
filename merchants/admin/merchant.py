# merchants/admin/merchant.py

from django.contrib import admin

from lib.erp_base.admin import BaseAdmin
from merchants.models import Merchant


@admin.register(Merchant)
class MerchantAdmin(BaseAdmin):
    list_display = [
        "id",
        "user",
        "get_phone",
        "get_national_id"
    ]
    search_fields = [
        "user__username",
        "user__profile__national_id"
    ]

    @admin.display(description="شماره تلفن")
    def get_phone(self, obj):
        return obj.user.profile.phone_number if hasattr(
            obj.user, "profile"
        ) else "-"

    @admin.display(description="کد ملی")
    def get_national_id(self, obj):
        return obj.user.profile.national_id if hasattr(
            obj.user, "profile"
        ) else "-"

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False
