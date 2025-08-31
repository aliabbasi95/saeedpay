# credit/admin/statement.py

from django.contrib import admin, messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from credit.models import Statement
from credit.models.statement_line import StatementLine
from credit.utils.choices import StatementLineType
from lib.erp_base.admin import BaseAdmin, BaseInlineAdmin


class StatementLineInline(BaseInlineAdmin):
    model = StatementLine
    extra = 0
    can_delete = False
    show_change_link = True
    ordering = ("-created_at",)
    fields = (
        "jalali_creation_time",
        "type_badge",
        "amount_colored",
        "transaction_link",
        "description",
    )
    readonly_fields = fields

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("transaction")
        return qs.order_by("-created_at")

    def has_add_permission(self, request, obj=None):
        return False

    # ----- inline displays -----
    @admin.display(description=_("نوع"), ordering="type")
    def type_badge(self, obj):
        colors = {
            StatementLineType.PURCHASE: "#dc3545",
            StatementLineType.PAYMENT: "#28a745",
            StatementLineType.FEE: "#6c757d",
            StatementLineType.PENALTY: "#d39e00",
            StatementLineType.INTEREST: "#0d6efd",
        }
        color = colors.get(obj.type, "#6c757d")
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>', color,
            obj.get_type_display()
        )

    @admin.display(description=_("مبلغ"), ordering="amount")
    def amount_colored(self, obj):
        if obj.amount is None:
            return "-"
        val = int(obj.amount)
        color = "#28a745" if val >= 0 else "#dc3545"
        formatted = format(val, ",d")
        return format_html(
            '<span style="color:{};direction:ltr;">{}</span>', color, formatted
        )

    @admin.display(description=_("تراکنش"), ordering="transaction")
    def transaction_link(self, obj):
        if not obj.transaction_id:
            return "-"
        url = reverse(
            "admin:wallets_transaction_change", args=[obj.transaction_id]
        )
        return format_html('<a href="{}">{}</a>', url, obj.transaction_id)


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
        "jalali_creation_time",
        "jalali_update_time",
    ]

    fieldsets = (
        (_("اطلاعات کاربر"), {
            "fields": (
                "user",
            )
        }),
        (_("دوره صورتحساب"), {
            "fields": (
                "year",
                "month",
                "status"
            )
        }),
        (_("مانده‌ها"), {
            "fields": (
                "opening_balance",
                "closing_balance",
                "total_debit",
                "total_credit"
            )
        }),
        (_("زمان‌بندی"), {
            "fields": (
                "due_date",
                "paid_at",
                "closed_at"
            )
        }),
        (_("اطلاعات پیگیری"), {
            "fields": (
                "reference_code",
                "jalali_creation_time",
                "jalali_update_time"
            )
        }),
    )

    actions = ["action_recalculate_balances", "action_close_current"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    # ----- displays -----
    @admin.display(description=_("دوره"))
    def period(self, obj):
        return f"{obj.year}/{obj.month:02d}"

    @admin.display(description=_("مانده اول دوره"), ordering="opening_balance")
    def opening_balance_display(self, obj):
        return f"{int(obj.opening_balance):,} ریال"

    @admin.display(
        description=_("مانده پایان دوره"), ordering="closing_balance"
    )
    def closing_balance_display(self, obj):
        return f"{int(obj.closing_balance):,} ریال"

    @admin.display(description=_("مجموع بدهکار"), ordering="total_debit")
    def total_debit_display(self, obj):
        return f"{int(obj.total_debit):,} ریال"

    @admin.display(description=_("مجموع بستانکار"), ordering="total_credit")
    def total_credit_display(self, obj):
        return f"{int(obj.total_credit):,} ریال"

    @admin.display(description=_("وضعیت"), ordering="status")
    def status_badge(self, obj):
        colors = {
            "current": "#17a2b8",
            "pending_payment": "#ffc107",
            "closed_no_penalty": "#28a745",
            "closed_with_penalty": "#6f42c1",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>', color,
            obj.get_status_display()
        )

    @admin.display(description=_("روزهای تاخیر"))
    def overdue_days(self, obj):
        if obj.due_date and timezone.now() > obj.due_date:
            return (timezone.now() - obj.due_date).days
        return "-"

    @admin.display(description=_("جریمهٔ تجمعی"))
    def penalty_to_date_display(self, obj):
        amount = obj.compute_penalty_amount()
        return f"{amount:,} ریال" if amount else "-"

    @admin.display(description=_("حداقل پرداخت"))
    def minimum_payment_display(self, obj):
        amount = obj.calculate_minimum_payment_amount()
        return f"{amount:,} ریال" if amount else "-"

    # ----- actions -----
    @admin.action(description=_("بازمحاسبه مانده‌ها"))
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

    @admin.action(description=_("بستن صورتحساب‌های جاری انتخاب‌شده"))
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
