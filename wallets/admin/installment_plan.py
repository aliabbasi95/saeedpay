# wallets/admin/installment_plan.py

from django.contrib import admin
from django.urls import reverse, NoReverseMatch
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from lib.erp_base.admin import BaseAdmin
from wallets.models import InstallmentPlan
from wallets.utils.choices import InstallmentPlanStatus


@admin.register(InstallmentPlan)
class InstallmentPlanAdmin(BaseAdmin):
    list_display = (
        "id",
        "user_link",
        "status_badge",
        "total_amount_display",
        "duration_months",
        "period_months",
        "interest_rate",
        "created_at",
        "closed_at",
        "jalali_creation_time",
    )
    list_filter = ("status", "duration_months", "period_months", "created_at")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "description",
    )
    readonly_fields = (
        "user",
        "source_type",
        "source_object_id",
        "total_amount",
        "duration_months",
        "period_months",
        "interest_rate",
        "initial_transaction",
        "description",
        "created_by",
        "closed_at",
        "status",
        "jalali_creation_time",
        "jalali_update_time",
    )
    fieldsets = (
        (_("User & Source"), {
            "fields": ("user", "source_type", "source_object_id", "created_by")
        }),
        (_("Financials"), {
            "fields": ("total_amount", "duration_months", "period_months",
                       "interest_rate")
        }),
        (_("Relations"), {"fields": ("initial_transaction",)}),
        (_("Status & Timeline"), {"fields": ("status", "closed_at")}),
        (_("Description"), {"fields": ("description",)}),
        (_("Timestamps"),
         {"fields": ("jalali_creation_time", "jalali_update_time")}),
    )
    list_select_related = ("user", "initial_transaction")
    autocomplete_fields = ("user", "initial_transaction")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    # ------- helpers -------
    def _link(self, app, model, pk, text):
        try:
            url = reverse(f"admin:{app}_{model}_change", args=[pk])
            return format_html('<a href="{}">{}</a>', url, text)
        except NoReverseMatch:
            return text

    @admin.display(description=_("User"), ordering="user")
    def user_link(self, obj: InstallmentPlan):
        label = getattr(obj.user, "username", f"#{obj.user_id}")
        return self._link("auth", "user", obj.user_id, label)

    @admin.display(description=_("Status"), ordering="status")
    def status_badge(self, obj: InstallmentPlan):
        colors = {
            InstallmentPlanStatus.ACTIVE: "#28a745",
            InstallmentPlanStatus.CLOSED: "#6c757d",
        }
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            colors.get(obj.status, "#6c757d"),
            obj.get_status_display()
        )

    @admin.display(description=_("Total Amount"), ordering="total_amount")
    def total_amount_display(self, obj: InstallmentPlan):
        return format_html(
            '<span style="direction:ltr;">{:,}</span>',
            int(obj.total_amount or 0)
        )

    # read-only admin
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
