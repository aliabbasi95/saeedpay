from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from wallets.models import Installment


@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):
    """
    Admin interface for the Installment model.
    """
    list_display = [
        "id",
        "plan",
        "due_date",
        "amount_display",
        "amount_paid_display",
        "status",
        "paid_at",
    ]
    list_filter = ["status", "due_date"]
    search_fields = [
        "id",
        "plan__request__reference_code",
        "plan__request__customer__user__username",
        "plan__request__customer__user__profile__first_name",
        "plan__request__customer__user__profile__last_name",
    ]

    # Base readonly fields
    base_readonly_fields = [
        "amount_paid",
        "penalty_amount",
        "paid_at",
        "transaction",
    ]

    def get_readonly_fields(self, request, obj=None):
        """
        Make property fields readonly only on the change form.
        """
        if obj:  # obj is not None, so this is a change page
            return self.base_readonly_fields + ["is_overdue", "current_penalty"]
        # This is an add page, obj is None
        return self.base_readonly_fields

    def get_fieldsets(self, request, obj=None):
        """
        Show different fieldsets for add and change forms.
        Calculated properties are only shown on the change form.
        """
        add_fieldsets = (
            (_("اطلاعات قسط"), {
                "fields": ("plan", "due_date", "amount")
            }),
            (_("وضعیت و یادداشت"), {
                "fields": ("status", "note")
            }),
        )

        change_fieldsets = (
            (_("اطلاعات قسط"), {
                "fields": ("plan", "due_date", "amount")
            }),
            (_("اطلاعات پرداخت"), {
                "fields": ("amount_paid", "penalty_amount", "paid_at", "transaction")
            }),
            (_("وضعیت و یادداشت"), {
                "fields": ("status", "is_overdue", "current_penalty", "note")
            }),
        )

        if obj:
            return change_fieldsets
        return add_fieldsets

    @admin.display(description=_("مبلغ قسط"), ordering='amount')
    def amount_display(self, obj):
        """
        Formats the amount with comma separators.
        """
        return f"{obj.amount:,} ریال"

    @admin.display(description=_("مبلغ پرداخت‌شده"), ordering='amount_paid')
    def amount_paid_display(self, obj):
        """
        Formats the paid amount with comma separators.
        """
        return f"{obj.amount_paid:,} ریال"
