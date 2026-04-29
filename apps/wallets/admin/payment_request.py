# wallets/admin/payment_request.py

from django.contrib import admin
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from lib.erp_base.admin import BaseAdmin
from wallets.models import PaymentRequest
from wallets.utils.choices import PaymentRequestStatus


@admin.register(PaymentRequest)
class PaymentRequestAdmin(BaseAdmin):
    list_display = (
        "reference_code",
        "status_badge",
        "flow_type",
        "amount_display",
        "store_link",
        "paid_by_link",
        "paid_wallet_link",
        "expires_at",
        "paid_at",
        "completed_at",
        "jalali_creation_time",
    )
    list_filter = ("status", "flow_type", "store", "created_at", "expires_at")
    search_fields = (
        "reference_code",
        "description",
        "external_guid",
        "store__name",
        "paid_by__username",
        "paid_wallet__wallet_number",
    )
    readonly_fields = (
        "reference_code",
        "status",
        "flow_type",
        "amount",
        "description",
        "external_guid",
        "return_url",
        "store",
        "customer",
        "paid_by",
        "paid_wallet",
        "expires_at",
        "created_expires_at",
        "merchant_confirm_expires_at",
        "paid_at",
        "completed_at",
        "cancelled_at",
        "expired_at",
        "jalali_creation_time",
        "jalali_update_time",
    )
    fieldsets = (
        (_("شناسه"), {"fields": ("reference_code",)}),
        (
            _("جزئیات"),
            {
                "fields": (
                    "status",
                    "flow_type",
                    "amount",
                    "description",
                    "external_guid",
                    "return_url",
                )
            },
        ),
        (
            _("ارتباطات"),
            {
                "fields": (
                    "store",
                    "customer",
                    "paid_by",
                    "paid_wallet",
                )
            },
        ),
        (
            _("زمان‌بندی"),
            {
                "fields": (
                    "expires_at",
                    "created_expires_at",
                    "merchant_confirm_expires_at",
                    "paid_at",
                    "completed_at",
                    "cancelled_at",
                    "expired_at",
                    "jalali_creation_time",
                    "jalali_update_time",
                )
            },
        ),
    )
    list_select_related = ("store", "customer", "paid_by", "paid_wallet")
    autocomplete_fields = ("paid_by", "paid_wallet")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    def _change_link(self, app_label, model_name, pk, text):
        try:
            url = reverse(f"admin:{app_label}_{model_name}_change", args=[pk])
            return format_html('<a href="{}">{}</a>', url, text)
        except NoReverseMatch:
            return text

    @admin.display(description=_("مبلغ"), ordering="amount")
    def amount_display(self, obj):
        return format_html(
            '<span style="direction:ltr;">{}</span>',
            format(int(obj.amount or 0), ",d"),
        )

    @admin.display(description=_("وضعیت"), ordering="status")
    def status_badge(self, obj):
        colors = {
            PaymentRequestStatus.CREATED: "#6c757d",
            PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION: "#17a2b8",
            PaymentRequestStatus.COMPLETED: "#28a745",
            PaymentRequestStatus.CANCELLED: "#dc3545",
            PaymentRequestStatus.EXPIRED: "#fd7e14",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.display(description=_("فروشگاه"), ordering="store")
    def store_link(self, obj):
        if not obj.store_id:
            return "-"
        return self._change_link("store", "store", obj.store_id, obj.store.name)

    @admin.display(description=_("پرداخت‌کننده"), ordering="paid_by")
    def paid_by_link(self, obj):
        if not obj.paid_by_id:
            return "-"
        return self._change_link("auth", "user", obj.paid_by_id, obj.paid_by.username)

    @admin.display(description=_("کیف پول"), ordering="paid_wallet")
    def paid_wallet_link(self, obj):
        if not obj.paid_wallet_id:
            return "-"
        return self._change_link(
            "wallets",
            "wallet",
            obj.paid_wallet_id,
            obj.paid_wallet.wallet_number,
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
