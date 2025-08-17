# tickets/admin/category.py

from django.contrib import admin

from lib.erp_base.admin import BaseAdmin
from tickets.models import TicketCategory


@admin.register(TicketCategory)
class TicketCategoryAdmin(BaseAdmin):
    list_display = [
        "id",
        "name",
        "description",
        "icon",
        "color",
    ]
    search_fields = ["name", "description"]

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False
