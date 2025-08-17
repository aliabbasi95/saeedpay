# tickets/admin/message.py

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from lib.erp_base.admin import BaseAdmin, BaseInlineAdmin
from tickets.models import TicketMessage, TicketMessageAttachment


class TicketMessageAttachmentInline(BaseInlineAdmin):
    model = TicketMessageAttachment
    fields = ("file",)
    extra = 0

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TicketMessage)
class TicketMessageAdmin(BaseAdmin):
    list_display = (
        "id",
        "ticket",
        "sender",
        "short_content",
        "jalali_creation_date_time",
    )
    search_fields = ("ticket__title", "ticket__user__username", "content")
    list_select_related = ("ticket",)
    inlines = [TicketMessageAttachmentInline]

    @admin.display(description=_("خلاصه پیام"))
    def short_content(self, obj: TicketMessage) -> str:
        return (obj.content[:64] + "…") if len(obj.content) > 64 else obj.content

    def has_change_permission(self, request, obj=None):
        # پیام‌ها پس از ثبت قابل ویرایش نیستند
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        # پیام جدید از مسیر inline در جزئیات تیکت ثبت می‌شود
        return False
