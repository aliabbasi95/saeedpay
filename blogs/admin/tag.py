# blogs/admin/tag.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from blogs.models import Tag
from lib.erp_base.admin import BaseAdmin


@admin.register(Tag)
class TagAdmin(BaseAdmin):
    """
    Lightweight Tag admin with color chip and readonly counters.
    """
    list_display = [
        "name",
        "slug",
        "color_display",
        "article_count",
        "is_active",
        "jalali_creation_date_time"
    ]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = [
        "article_count",
        "jalali_creation_date_time",
        "jalali_update_date_time"
    ]
    list_per_page = 50

    fieldsets = (
        (_("اطلاعات اصلی"),
         {"fields": ("name", "slug", "description", "color", "is_active")}),
        (_("آمار"), {"fields": ("article_count",), "classes": ("collapse",)}),
        (_("زمان‌بندی"), {
            "fields": ("jalali_creation_date_time", "jalali_update_date_time"),
            "classes": ("collapse",)
        }),
    )

    @admin.display(description=_("رنگ"))
    def color_display(self, obj):
        # Simple color chip; consider dynamic text color if you expect very light backgrounds.
        return format_html(
            '<span style="background-color:{}; color:#fff; padding:2px 8px; border-radius:3px;">{}</span>',
            obj.color,
            obj.color,
        )
