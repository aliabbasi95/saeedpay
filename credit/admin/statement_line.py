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
        "type",
        "amount_colored",
        "transaction_id",
        "jalali_creation_time",
        "description",
    )
    list_filter = (
        "type",
        "created_at",
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

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "statement", "transaction"
        )

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
            '<span style="color:{};font-weight:600;">{}</span>',
            color,
            obj.get_type_display(),
        )

    type_badge.short_description = _("نوع")

    def statement_link(self, obj):
        url = reverse("admin:credit_statement_change", args=[obj.statement_id])
        label = obj.statement.reference_code or obj.statement_id
        return format_html('<a href="{}">{}</a>', url, label)

    statement_link.short_description = _("صورتحساب")

    def amount_colored(self, obj):
        if obj.amount is None:
            return "-"
        val = int(obj.amount)
        color = "#28a745" if val >= 0 else "#dc3545"
        return format_html(
            '<span style="color:{};direction:ltr;">{:,}</span>', color, val
        )

    amount_colored.short_description = _("مبلغ")
