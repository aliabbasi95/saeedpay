# credit/admin/credit_limit.py

from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from credit.models import CreditLimit
from lib.erp_base.admin import BaseAdmin


@admin.register(CreditLimit)
class CreditLimitAdmin(BaseAdmin):
    list_display = [
        "reference_code",
        "user",
        "approved_limit_display",
        "available_limit_display",
        "is_active_badge",
        "expiry_date",
        "jalali_creation_time",
    ]
    list_filter = [
        "is_active",
        "expiry_date",
        "created_at",
        ("user", admin.RelatedOnlyFieldListFilter),
    ]
    search_fields = [
        "reference_code",
        "user__username",
        "user__first_name",
        "user__last_name",
    ]
    readonly_fields = [
        "reference_code",
        "available_limit_display",
        "jalali_creation_time",
        "jalali_update_time",
    ]
    fieldsets = (
        (_("اطلاعات کاربر"), {"fields": ("user",)}),
        (_("محدودیت اعتباری"),
         {"fields": ("approved_limit", "available_limit_display")}),
        (_("وضعیت و اعتبار"),
         {"fields": ("is_active", "expiry_date", "grace_period_days")}),
        (_("اطلاعات پیگیری"),
         {
             "fields": (
                 "reference_code",
                 "jalali_creation_time",
                 "jalali_update_time"
             )
         }),
    )
    actions = ["activate_selected"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    # ----- displays -----
    @admin.display(description=_("حد اعتباری"), ordering="approved_limit")
    def approved_limit_display(self, obj):
        return f"{int(obj.approved_limit):,} ریال"

    @admin.display(description=_("اعتبارِ باقی‌مانده"))
    def available_limit_display(self, obj):
        if obj.approved_limit is None:
            return "-"
        return f"{int(obj.available_limit):,} ریال"

    @admin.display(description=_("وضعیت"), ordering="is_active")
    def is_active_badge(self, obj):
        color = "#28a745" if obj.is_active else "#6c757d"
        label = _("فعال") if obj.is_active else _("غیرفعال")
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>', color, label
        )

    # ----- actions -----
    @admin.action(description=_("فعال‌سازی موارد انتخاب‌شده"))
    def activate_selected(self, request, queryset):
        count = 0
        for limit in queryset:
            try:
                limit.activate()
                count += 1
            except Exception as e:
                self.message_user(
                    request, f"خطا در فعال‌سازی {limit.reference_code}: {e}",
                    messages.ERROR
                )
        if count:
            self.message_user(
                request, f"{count} رکورد فعال شد.", messages.SUCCESS
            )
