# wallets/admin/installment_plan.py

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from wallets.models import InstallmentPlan, Installment, InstallmentRequest
from wallets.utils.choices import InstallmentPlanStatus, InstallmentSourceType


class InstallmentInline(admin.TabularInline):
    """
    Inline admin descriptor for Installment objects.
    This will be used within the InstallmentPlan admin to show its installments.
    """
    model = Installment
    fields = [
        "due_date",
        "amount_display",
        "status",
        "amount_paid_display",
        "paid_at",
        "view_installment_link",
    ]
    readonly_fields = fields
    extra = 0
    verbose_name = _("قسط")
    verbose_name_plural = _("جدول اقساط")

    # def has_add_permission(self, request, obj=None):
    #     return False
    #
    # def has_delete_permission(self, request, obj=None):
    #     return False

    @admin.display(description=_("مبلغ قسط"))
    def amount_display(self, obj):
        # FIX: Check if obj.amount is None before formatting
        if obj.amount is not None:
            return f"{obj.amount:,} ریال"
        return "۰ ریال"

    @admin.display(description=_("مبلغ پرداخت‌شده"))
    def amount_paid_display(self, obj):
        # FIX: Check if obj.amount_paid is None before formatting
        if obj.amount_paid is not None:
            return f"{obj.amount_paid:,} ریال"
        return "۰ ریال"

    @admin.display(description=_("مشاهده"))
    def view_installment_link(self, obj):
        if obj.id:
            url = reverse('admin:wallets_installment_change', args=[obj.id])
            return format_html('<a href="{}">ویرایش</a>', url)
        return "-"


@admin.register(InstallmentPlan)
class InstallmentPlanAdmin(admin.ModelAdmin):
    """
    Admin interface for the InstallmentPlan model.
    """
    inlines = [InstallmentInline]  # This is the key part to show the installments

    list_display = [
        "id",
        "user",
        "total_amount_display",
        "duration_months",
        "interest_rate",
        "status_colored",
        "source_object_link",
        "created_at",
    ]
    list_filter = ["status", "duration_months", "created_at"]
    search_fields = [
        "id",
        "user__username",
        "user__profile__first_name",
        "user__profile__last_name",
        "source_object_id",  # Allows searching for the original request ID
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "closed_at",
        "created_by",
        "source_object_link",
    ]
    # autocomplete_fields = ["user", "initial_transaction"]

    fieldsets = (
        (_("اطلاعات اصلی"), {
            "fields": ("user", "status", "source_object_link")
        }),
        (_("شرایط مالی"), {
            "fields": (
                "total_amount",
                "duration_months",
                "period_months",
                "interest_rate",
            )
        }),
        (_("اطلاعات سیستمی"), {
            "fields": ("initial_transaction", "description", "created_by", "closed_at")
        }),
    )

    @admin.display(description=_("مبلغ کل"), ordering='total_amount')
    def total_amount_display(self, obj):
        return f"{obj.total_amount:,} ریال"

    @admin.display(description=_("وضعیت"))
    def status_colored(self, obj):
        color_map = {
            InstallmentPlanStatus.ACTIVE: "blue",
            InstallmentPlanStatus.PAID_OFF: "green",
            InstallmentPlanStatus.OVERDUE: "orange",
            InstallmentPlanStatus.CANCELLED: "dimgray",
        }
        color = color_map.get(obj.status, "black")
        return format_html(
            '<span style="color: {};">{}</span>', color, obj.get_status_display()
        )

    @admin.display(description=_("منبع"))
    def source_object_link(self, obj):
        """
        Creates a clickable link to the source object (e.g., InstallmentRequest).
        """
        source = obj.get_source_object()
        if not source:
            return "-"

        # Customize based on the source type
        if obj.source_type == InstallmentSourceType.BNPL and isinstance(source, InstallmentRequest):
            url = reverse('admin:wallets_installmentrequest_change', args=[source.id])
            return format_html('<a href="{}">درخواست #{}</a>', url, source.reference_code)

        # Add other source types here if needed
        # elif obj.source_type == ...

        return f"{obj.get_source_type_display()}: {source.id}"