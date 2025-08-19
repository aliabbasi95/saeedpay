# tickets/admin/category.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from lib.erp_base.admin import BaseAdmin
from tickets.models import TicketCategory


@admin.register(TicketCategory)
class TicketCategoryAdmin(BaseAdmin):
    list_display = (
        "id",
        "name",
        "description_short",
        "icon_badge",
        "color_tag"
    )
    list_display_links = ("id", "name")
    search_fields = ("name", "description")
    list_per_page = 30
    ordering = ("id",)
    fieldsets = (
        (_("اطلاعات"), {"fields": ("name", "description", "icon", "color")}),
    )

    @admin.display(description=_("توضیح"), ordering="description")
    def description_short(self, obj: TicketCategory):
        if not obj.description:
            return "-"
        return (obj.description[:60] + "…") if len(
            obj.description
        ) > 60 else obj.description

    @admin.display(description=_("آیکون"))
    def icon_badge(self, obj: TicketCategory):
        return format_html(
            '<code style="font-size:12px">{}</code>', obj.icon or "-"
        )

    @admin.display(description=_("رنگ"))
    def color_tag(self, obj: TicketCategory):
        if not obj.color:
            return "-"
        return format_html(
            '<span style="display:inline-block;width:1.2rem;height:1.2rem;'
            'border-radius:.35rem;border:1px solid #ccc;vertical-align:middle;'
            'background:{}"></span> <code style="margin-right:.4rem">{}</code>',
            obj.color, obj.color
        )
