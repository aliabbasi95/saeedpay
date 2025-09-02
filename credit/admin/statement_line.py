# credit/admin/statement_line.py

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from credit.models.statement_line import StatementLine
from credit.utils.choices import StatementLineType
from lib.erp_base.admin import BaseAdmin


@admin.register(StatementLine)
class StatementLineAdmin(BaseAdmin):
    list_display = (
        "id",
        "statement_link",
        "type_badge",
        "amount_colored",
        "is_voided",
        "transaction_id",
        "jalali_creation_time",
        "description",
    )
    list_filter = (
        "type",
        "created_at",
        "is_voided",
        "statement__status",
        "statement__year",
        "statement__month",
    )
    search_fields = (
        "description",
        "statement__reference_code",
        "transaction__id",
        "statement__user__username",
        "statement__user__first_name",
        "statement__user__last_name",
    )
    date_hierarchy = "created_at"
    autocomplete_fields = ("statement", "transaction")
    list_select_related = ("statement", "transaction")
    ordering = ("-created_at",)
    actions = ("action_void_selected",)

    def get_queryset(self, request):
        # include voided lines as well
        return StatementLine.all_objects.select_related(
            "statement", "transaction"
        )

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

    @admin.display(description=_("صورتحساب"), ordering="statement")
    def statement_link(self, obj):
        url = reverse("admin:credit_statement_change", args=[obj.statement_id])
        label = obj.statement.reference_code or obj.statement_id
        return format_html('<a href="{}">{}</a>', url, label)

    @admin.display(description=_("مبلغ"), ordering="amount")
    def amount_colored(self, obj):
        if obj.amount is None:
            return "-"
        val = int(obj.amount)
        color = "#6c757d" if obj.is_voided else (
            "#28a745" if val >= 0 else "#dc3545")
        formatted = format(val, ",d")
        style = "text-decoration:line-through;" if obj.is_voided else ""
        return format_html(
            '<span style="color:{};{};direction:ltr;">{}</span>', color, style,
            formatted
        )

    @admin.action(description=_("باطل کردن سطرهای انتخاب‌شده"))
    def action_void_selected(self, request, queryset):
        done = 0
        for line in queryset:
            try:
                if line.void(by=request.user, reason="Admin action"):
                    done += 1
            except Exception:
                continue
        if done:
            self.message_user(request, _("%d line(s) voided.") % done)
