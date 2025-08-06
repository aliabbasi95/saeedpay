# wallets/admin/installment_request.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from wallets.models import InstallmentRequest


@admin.register(InstallmentRequest)
class InstallmentRequestAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "reference_code",
        "customer_name",
        "national_id",
        "store",
        "proposal_amount_display",
        "confirmed_amount_display",
        "status_colored",
        "store_confirmed_at",
        "user_confirmed_at",
        "view_plan_link",
    ]
    list_filter = [
        "status",
        "store",
        "store_confirmed_at",
        "user_confirmed_at",
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
        "store_confirmed_at",
        "user_confirmed_at",
    ]
    autocomplete_fields = ["store", "customer", "contract"]
    fieldsets = (
        (_("اطلاعات پایه"), {
            "fields": ("reference_code", "store", "customer", "national_id",
                       "contract")
        }),
        (_("مبالغ و تاییدات"), {
            "fields": (
                "proposal_amount", "credit_limit_amount", "confirmed_amount",
                "store_confirmed_at", "user_confirmed_at"
            )
        }),
        (_("برنامه بازپرداخت"), {
            "fields": ("duration_months", "period_months")
        }),
        (_("وضعیت"), {
            "fields": ("status",)
        }),
    )

    def customer_name(self, obj):
        return obj.customer.user.profile.full_name

    customer_name.short_description = _("نام مشتری")

    def proposal_amount_display(self, obj):
        return f"{obj.proposal_amount:,} تومان"

    proposal_amount_display.short_description = _("مبلغ پیشنهادی")

    def confirmed_amount_display(self, obj):
        if obj.confirmed_amount:
            return f"{obj.confirmed_amount:,} تومان"
        return "-"

    confirmed_amount_display.short_description = _("مبلغ تایید شده")

    def status_colored(self, obj):
        color = {
            "created": "gray",
            "user_confirmed": "orange",
            "store_confirmed": "green",
            "rejected": "red",
        }.get(obj.status, "black")
        return format_html(
            '<span style="color: {};">{}</span>',
            color, obj.get_status_display()
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
