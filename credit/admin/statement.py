# credit/admin/statement.py

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from credit.models import Statement


@admin.register(Statement)
class StatementAdmin(admin.ModelAdmin):
    list_display = [
        "reference_code",
        "user",
        "year",
        "month",
        "status",
        "closing_balance",
        "penalty_amount",
        "grace_date",
        "created_at",
    ]

    list_filter = ["status", "year", "month", "created_at"]

    search_fields = [
        "reference_code",
        "user__username",
        "user__first_name",
        "user__last_name",
    ]

    readonly_fields = [
        "reference_code",
        "total_debit",
        "total_credit",
        "closing_balance",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (_("اطلاعات کاربر"), {"fields": ("user",)}),
        (
            _("دوره صورتحساب"),
            {
                "fields": (
                    "year",
                    "month",
                    "status",
                )
            },
        ),
        (
            _("مانده‌ها"),
            {
                "fields": (
                    "opening_balance",
                    "closing_balance",
                    "total_debit",
                    "total_credit",
                )
            },
        ),
        (
            _("زمان‌بندی و جریمه"),
            {
                "fields": (
                    "grace_date",
                    "paid_at",
                )
            },
        ),
        (_("تراکنش‌ها"), {"fields": ("transactions",)}),
        (
            _("اطلاعات پیگیری"),
            {
                "fields": (
                    "reference_code",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def penalty_amount(self, obj):
        """Display calculated penalty amount"""
        penalty = obj.calculate_penalty()
        if penalty > 0:
            return f"{penalty:,} ریال"
        return "-"

    penalty_amount.short_description = _("مقدار جریمه")

    def has_delete_permission(self, request, obj=None):
        return False
