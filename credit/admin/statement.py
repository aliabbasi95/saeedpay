# credit/admin/statement.py

from django.contrib import admin, messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from credit.models import Statement
from credit.models.statement_line import StatementLine
from lib.erp_base.admin import BaseAdmin, BaseInlineAdmin


class StatementLineInline(BaseInlineAdmin):
    model = StatementLine
    extra = 0
    can_delete = False
    show_change_link = True
    ordering = ("-created_at",)
    fields = (
        "jalali_creation_time",
        "type",
        "amount",
        "amount_colored",
        "transaction_link",
        "description"
    )
    readonly_fields = (
        "jalali_creation_time",
        "type",
        "amount_colored",
        "transaction_link",
        "description"
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("transaction")
        return qs.order_by("-created_at")

    def type_badge(self, obj):
        from credit.utils.choices import StatementLineType
        colors = {
            StatementLineType.PURCHASE: "#dc3545",
            StatementLineType.PAYMENT: "#28a745",
            StatementLineType.FEE: "#6c757d",
            StatementLineType.PENALTY: "#d39e00",
            StatementLineType.INTEREST: "#0d6efd",
        }
        color = colors.get(obj.type, "#6c757d")
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            color,
            obj.get_type_display(),
        )

    type_badge.short_description = _("نوع")

    def amount_colored(self, obj):
        print(obj)
        print(obj.amount)
        if not obj or obj.amount is None:
            return "-"
        val = int(obj.amount)
        print(2)
        color = "#28a745" if val >= 0 else "#dc3545"
        print(3)
        formatted = f"{int(val):,}"
        try:
            print(format_html(
            '<span style="color:{};direction:ltr;">{}</span>',
            color,
            formatted,
        )
    )
        except Exception as e:
            print(e)
        print(4)
        return format_html(
            '<span style="color:{};direction:ltr;">{}</span>',
            color,
            formatted,
        )

    amount_colored.short_description = _("مبلغ")

    def transaction_link(self, obj):
        if not obj.transaction_id:
            return "-"
        url = reverse(
            "admin:wallets_transaction_change", args=[obj.transaction_id]
        )
        return format_html('<a href="{}">{}</a>', url, obj.transaction_id)

    transaction_link.short_description = _("تراکنش")


@admin.register(Statement)
class StatementAdmin(BaseAdmin):
    list_display = [
        "reference_code",
        "user",
        "period",
        "status_badge",
        "opening_balance_display",
        "total_debit_display",
        "total_credit_display",
        "closing_balance_display",
        "due_date",
        "overdue_days",
        "minimum_payment_display",
        "penalty_to_date_display",
        "jalali_creation_time",
    ]
    inlines = (StatementLineInline,)
    list_filter = ["status", "year", "month", "due_date", "created_at"]
    search_fields = [
        "reference_code",
        "user__username",
        "user__first_name",
        "user__last_name",
    ]
    date_hierarchy = "created_at"

    readonly_fields = [
        "reference_code",
        "total_debit",
        "total_credit",
        "closing_balance",
        "due_date",
        "closed_at",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (_("اطلاعات کاربر"), {"fields": ("user",)}),
        (_("دوره صورتحساب"), {"fields": ("year", "month", "status")}),
        (_("مانده‌ها"), {
            "fields": ("opening_balance", "closing_balance", "total_debit",
                       "total_credit")
        }),
        (_("زمان‌بندی"), {"fields": ("due_date", "paid_at", "closed_at")}),
        (_("اطلاعات پیگیری"),
         {"fields": ("reference_code", "created_at", "updated_at")}),
    )

    actions = ["action_recalculate_balances", "action_close_current"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    # ===== Displays =====
    def period(self, obj):
        return f"{obj.year}/{obj.month:02d}"

    period.short_description = _("دوره")

    def opening_balance_display(self, obj):
        return f"{int(obj.opening_balance):,} ریال"

    opening_balance_display.short_description = _("مانده اول دوره")

    def closing_balance_display(self, obj):
        return f"{int(obj.closing_balance):,} ریال"

    closing_balance_display.short_description = _("مانده پایان دوره")

    def total_debit_display(self, obj):
        return f"{int(obj.total_debit):,} ریال"

    total_debit_display.short_description = _("مجموع بدهکار")

    def total_credit_display(self, obj):
        return f"{int(obj.total_credit):,} ریال"

    total_credit_display.short_description = _("مجموع بستانکار")

    def status_badge(self, obj):
        colors = {
            "current": "#17a2b8",
            "pending_payment": "#ffc107",
            "overdue": "#dc3545",
            "closed_no_penalty": "#28a745",
            "closed_with_penalty": "#6f42c1"
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>', color,
            obj.get_status_display()
        )

    status_badge.short_description = _("وضعیت")

    def overdue_days(self, obj):
        if obj.due_date and timezone.now() > obj.due_date:
            return (timezone.now() - obj.due_date).days
        return "-"

    overdue_days.short_description = _("روزهای تاخیر")

    def penalty_to_date_display(self, obj):
        amount = obj.compute_penalty_amount()
        return f"{amount:,} ریال" if amount else "-"

    penalty_to_date_display.short_description = _("جریمه تاکنون")

    def minimum_payment_display(self, obj):
        amount = obj.calculate_minimum_payment_amount()
        return f"{amount:,} ریال" if amount else "-"

    minimum_payment_display.short_description = _("حداقل پرداخت")

    # ===== Actions =====
    def action_recalculate_balances(self, request, queryset):
        updated = 0
        for stmt in queryset:
            try:
                stmt.update_balances()
                updated += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"خطا در محاسبه مانده برای {stmt.reference_code}: {e}",
                    level=messages.ERROR,
                )
        if updated:
            self.message_user(
                request, f"{updated} صورتحساب به‌روزرسانی شد.",
                level=messages.SUCCESS
            )

    action_recalculate_balances.short_description = _("بازمحاسبه مانده‌ها")

    def action_close_current(self, request, queryset):
        closed = 0
        for stmt in queryset.filter(status="current"):
            try:
                stmt.close_statement()
                closed += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"خطا در بستن صورتحساب {stmt.reference_code}: {e}",
                    level=messages.ERROR,
                )
        if closed:
            self.message_user(
                request, f"{closed} صورتحساب جاری بسته شد.",
                level=messages.SUCCESS
            )

    action_close_current.short_description = _(
        "بستن صورتحساب‌های جاری انتخاب‌شده"
    )
