# banking/admin/bank.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from lib.erp_base.admin import BaseAdmin
from ..models import Bank


@admin.register(Bank)
class BankAdmin(BaseAdmin):
    list_display = (
        "name",
        "logo_thumb",
        "color_swatch",
        "jalali_creation_date_time",
        "jalali_update_date_time"
    )
    search_fields = ("name", "color")
    ordering = ("name",)
    readonly_fields = (
        "created_at",
        "updated_at",
        "logo_preview",
        "color_swatch"
    )
    fieldsets = (
        (_("اطلاعات اصلی"), {
            "fields": (
                "name",
                "logo",
                "logo_preview",
                "color",
                "color_swatch"
            ),
        }),
    )

    def get_search_fields(self, request):
        return self.search_fields

    def logo_thumb(self, obj: Bank):
        if not obj.logo:
            return "—"
        return format_html(
            '<img src="{}" style="height:28px;border-radius:4px;" />',
            obj.logo.url
        )

    logo_thumb.short_description = _("لوگو")

    def logo_preview(self, obj: Bank):
        if not obj.logo:
            return "—"
        return format_html(
            '<img src="{}" style="max-height:80px;border-radius:6px;" />',
            obj.logo.url
        )

    logo_preview.short_description = _("پیش‌نمایش لوگو")

    def color_swatch(self, obj: Bank):
        if not obj.color:
            return "—"
        return format_html(
            '<span style="display:inline-block;width:18px;height:18px;border-radius:4px;'
            'border:1px solid #ddd;vertical-align:middle;background:{}"></span> '
            '<code style="margin-inline-start:6px">{}</code>',
            obj.color, obj.color
        )

    color_swatch.short_description = _("رنگ")
