# tickets/admin/message.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from lib.erp_base.admin import BaseAdmin, BaseInlineAdmin
from tickets.models import TicketMessage, TicketMessageAttachment


class TicketMessageAttachmentInline(BaseInlineAdmin):
    model = TicketMessageAttachment
    fields = ("file",)
    extra = 0
    can_delete = False
    show_change_link = True


@admin.register(TicketMessage)
class TicketMessageAdmin(BaseAdmin):
    list_display = (
        "id",
        "ticket_link",
        "sender_badge",
        "short_content",
        "jalali_creation_date_time",
    )
    search_fields = (
        "ticket__title",
        "ticket__user__username",
        "content",
        "ticket__id"
    )
    list_filter = ("sender",)
    list_select_related = ("ticket",)
    inlines = [TicketMessageAttachmentInline]
    fieldsets = (
        (None, {"fields": ("ticket", "sender", "content", "reply_to")}),
    )

    @admin.display(description=_("تیکت"))
    def ticket_link(self, obj: TicketMessage):
        return format_html(
            '<a href="/admin/tickets/ticket/{}/change/">#{} — {}</a>',
            obj.ticket_id, obj.ticket_id, obj.ticket.title
        )

    @admin.display(description=_("فرستنده"))
    def sender_badge(self, obj: TicketMessage):
        label = dict(obj.Sender.choices).get(obj.sender, obj.sender)
        tone = "#1769aa" if obj.sender == obj.Sender.STAFF else "#0f9d58"
        return format_html(
            '<span style="padding:.15rem .45rem;border-radius:.4rem;'
            'font-size:.75rem;color:#fff;background:{}">{}</span>', tone, label
        )

    @admin.display(description=_("خلاصه پیام"))
    def short_content(self, obj: TicketMessage) -> str:
        return (obj.content[:64] + "…") if len(
            obj.content
        ) > 64 else obj.content
