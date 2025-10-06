# wallets/admin/installment.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from lib.erp_base.admin import BaseAdmin
from wallets.models import Installment
from wallets.utils.choices import InstallmentStatus


@admin.register(Installment)
class InstallmentAdmin(BaseAdmin):
    list_display = (
        "id",
        "plan_link",
        "status_badge",
        "due_date",
        "amount_display",
        "amount_paid_display",
        "penalty_display",
        "is_overdue_badge",
        "transaction_link",
        "jalali_creation_time",
    )
    list_filter = ("status", "due_date", "created_at")
    search_fields = (
        "plan__id",
        "transaction__reference_code",
        "note",
    )
    readonly_fields = (
        "plan",
        "due_date",
        "amount",
        "amount_paid",
        "penalty_amount",
        "status",
        "paid_at",
        "transaction",
        "note",
        "jalali_creation_time",
        "jalali_update_time",
    )
    fieldsets = (
        (_("Plan"), {"fields": ("plan",)}),
        (_("Amounts & Dates"), {
            "fields": ("due_date", "amount", "amount_paid", "penalty_amount",
                       "paid_at")
        }),
        (_("Status & Txn"), {"fields": ("status", "transaction")}),
        (_("Note"), {"fields": ("note",)}),
        (_("Timestamps"),
         {"fields": ("jalali_creation_time", "jalali_update_time")}),
    )
    list_select_related = ("plan", "transaction")
    autocomplete_fields = ("plan", "transaction")
    ordering = ("due_date",)
    date_hierarchy = "due_date"

    # ------- helpers -------
    def _link(self, app, model, pk, label):
        from django.urls import reverse, NoReverseMatch
        try:
            url = reverse(f"admin:{app}_{model}_change", args=[pk])
            return format_html('<a href="{}">{}</a>', url, label)
        except NoReverseMatch:
            return label

    @admin.display(description=_("Plan"), ordering="plan")
    def plan_link(self, obj: Installment):
        return self._link(
            "wallets", "installmentplan", obj.plan_id, f"#{obj.plan_id}"
        )

    @admin.display(description=_("Transaction"))
    def transaction_link(self, obj: Installment):
        if not obj.transaction_id:
            return "-"
        from_code = getattr(
            obj.transaction, "reference_code", f"#{obj.transaction_id}"
        )
        return self._link(
            "wallets", "transaction", obj.transaction_id, from_code
        )

    @admin.display(description=_("Status"), ordering="status")
    def status_badge(self, obj: Installment):
        colors = {
            InstallmentStatus.UNPAID: "#ffc107",
            InstallmentStatus.PAID: "#28a745",
        }
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            colors.get(obj.status, "#6c757d"),
            obj.get_status_display()
        )

    @admin.display(description=_("Amount"), ordering="amount")
    def amount_display(self, obj: Installment):
        return format_html(
            '<span style="direction:ltr;">{:,}</span>', int(obj.amount or 0)
        )

    @admin.display(description=_("Paid"))
    def amount_paid_display(self, obj: Installment):
        return format_html(
            '<span style="direction:ltr;">{:,}</span>',
            int(obj.amount_paid or 0)
        )

    @admin.display(description=_("Penalty"))
    def penalty_display(self, obj: Installment):
        return format_html(
            '<span style="direction:ltr;">{:,}</span>',
            int(obj.penalty_amount or 0)
        )

    @admin.display(description=_("Overdue?"))
    def is_overdue_badge(self, obj: Installment):
        if obj.is_overdue:
            return format_html(
                '<span style="color:#dc3545;font-weight:600;">{}</span>',
                _("Yes")
            )
        return format_html(
            '<span style="color:#28a745;font-weight:600;">{}</span>', _("No")
        )

    # read-only admin
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
