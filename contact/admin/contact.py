# contact/admin/contact.py

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from contact.models.contact import Contact
from lib.erp_base.admin import BaseAdmin


@admin.register(Contact)
class ContactAdmin(BaseAdmin):
    """
    Clean admin for reviewing contact messages.
    - Compact list with message preview
    - Useful filters and searches
    - Read-only timestamps to prevent accidental edits
    """
    list_display = [
        "name",
        "email",
        "phone",
        "message_preview",
        "jalali_creation_date_time"
    ]
    list_filter = ["created_at"]
    search_fields = ["name", "email", "phone", "message"]
    readonly_fields = [
        "jalali_creation_date_time",
        "jalali_update_date_time",
        "email",
        "phone"
    ]
    ordering = ["-created_at"]
    list_per_page = 50

    fieldsets = (
        (_("فرم تماس"), {"fields": ("name", "email", "phone", "message")}),
        (_("زمان‌بندی"), {
            "fields": ("jalali_creation_date_time", "jalali_update_date_time"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description=_("پیش‌نمایش پیام"))
    def message_preview(self, obj):
        text = (obj.message or "").strip()
        return (text[:60] + "…") if len(text) > 60 else text
