from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from wallets.models import InstallmentRequest
from wallets.utils.choices import InstallmentRequestStatus


@admin.register(InstallmentRequest)
class InstallmentRequestAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "reference_code",
        "customer_name",
        "national_id",
        "store",
        "store_proposed_amount_display",
        "user_requested_amount_display",
        "system_approved_amount_display",
        "status_colored",
        "evaluated_at",
        "user_confirmed_at",
        "store_confirmed_at",
        "view_plan_link",
    ]
    list_filter = [
        "status",
        "store",
        "evaluated_at",
        "user_confirmed_at",
        "store_confirmed_at",
        "cancelled_at",
    ]
    search_fields = [
        "reference_code",
        "national_id",
        "customer__user__username",
        "customer__user__profile__first_name",
        "customer__user__profile__last_name",
    ]
    readonly_fields = [
        "reference_code",
        "requested_at",
        "evaluated_at",
        "user_confirmed_at",
        "store_confirmed_at",
        "cancelled_at",
    ]
    autocomplete_fields = ["store", "customer", "contract"]

    fieldsets = (
        (_("اطلاعات پایه"), {
            "fields": ("reference_code", "store", "customer", "national_id",
                       "contract")
        }),
        (_("مبالغ"), {
            "fields": (
                "store_proposed_amount",
                "user_requested_amount",
                "system_approved_amount",
            )
        }),
        (_("برنامه بازپرداخت"), {
            "fields": ("duration_months", "period_months")
        }),
        (_("زمان‌ها"), {
            "fields": ("requested_at", "evaluated_at", "user_confirmed_at",
                       "store_confirmed_at", "cancelled_at")
        }),
        (_("وضعیت و لغو"), {
            "fields": ("status", "cancel_reason")
        }),
    )

    def customer_name(self, obj):
        return getattr(
            obj.customer.user.profile, "full_name", obj.customer.user.username
        )

    customer_name.short_description = _("نام مشتری")

    def store_proposed_amount_display(self, obj):
        return f"{obj.store_proposed_amount:,} ریال"

    store_proposed_amount_display.short_description = _(
        "مبلغ پیشنهادی فروشگاه"
    )

    def user_requested_amount_display(self, obj):
        return f"{obj.user_requested_amount:,} ریال" if obj.user_requested_amount else "-"

    user_requested_amount_display.short_description = _("مبلغ درخواستی کاربر")

    def system_approved_amount_display(self, obj):
        return f"{obj.system_approved_amount:,} ریال" if obj.system_approved_amount else "-"

    system_approved_amount_display.short_description = _("مبلغ تاییدشده سیستم")

    def status_colored(self, obj):
        color_map = {
            InstallmentRequestStatus.CREATED: "gray",
            InstallmentRequestStatus.UNDERWRITING: "blue",
            InstallmentRequestStatus.VALIDATED: "orange",
            InstallmentRequestStatus.AWAITING_MERCHANT_CONFIRMATION: "purple",
            InstallmentRequestStatus.COMPLETED: "green",
            InstallmentRequestStatus.CANCELLED: "dimgray",
            InstallmentRequestStatus.REJECTED: "red",
        }
        color = color_map.get(obj.status, "black")
        return format_html(
            '<span style="color: {};">{}</span>', color,
            obj.get_status_display()
        )

    status_colored.short_description = _("وضعیت")

    def view_plan_link(self, obj):
        plan = obj.get_installment_plan()
        if plan:
            return format_html(
                '<a href="/admin/wallets/installmentplan/{}/change/">مشاهده قسط‌ها</a>',
                plan.id
            )
        return "-"

    view_plan_link.short_description = _("قسط‌بندی")
