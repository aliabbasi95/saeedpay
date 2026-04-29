# wallets/admin/payment.py

from django.contrib import admin
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from lib.erp_base.admin import BaseAdmin
from wallets.models import Payment
from wallets.utils.choices import PaymentStatus


@admin.register(Payment)
class PaymentAdmin(BaseAdmin):
    list_display = (
        "reference_code",
        "status_badge",
        "amount_display",
        "method",
        "flow_type",
        "payment_request_link",
        "payer_link",
        "payer_wallet_link",
        "completed_at",
        "jalali_creation_time",
    )
    list_filter = ("status", "method", "flow_type", "created_at")
    search_fields = (
        "reference_code",
        "payment_request__reference_code",
        "payer__username",
        "payer_wallet__wallet_number",
    )
    readonly_fields = (
        "reference_code",
        "payment_request",
        "payer",
        "payer_wallet",
        "amount",
        "method",
        "flow_type",
        "status",
        "authorization_expires_at",
        "merchant_confirm_expires_at",
        "completed_at",
        "cancelled_at",
        "expired_at",
        "failure_reason",
        "jalali_creation_time",
        "jalali_update_time",
    )
    list_select_related = ("payment_request", "payer", "payer_wallet")
    autocomplete_fields = ("payment_request", "payer", "payer_wallet")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    fieldsets = (
        (_("شناسه"), {"fields": ("reference_code",)}),
        (
            _("جزئیات"),
            {
                "fields": (
                    "payment_request",
                    "payer",
                    "payer_wallet",
                    "amount",
                    "method",
                    "flow_type",
                    "status",
                    "failure_reason",
                )
            },
        ),
        (
            _("زمان‌بندی"),
            {
                "fields": (
                    "authorization_expires_at",
                    "merchant_confirm_expires_at",
                    "completed_at",
                    "cancelled_at",
                    "expired_at",
                    "jalali_creation_time",
                    "jalali_update_time",
                )
            },
        ),
    )

    def _admin_change_link(self, app_label, model_name, pk, text):
        try:
            url = reverse(f"admin:{app_label}_{model_name}_change", args=[pk])
            return format_html('<a href="{}">{}</a>', url, text)
        except NoReverseMatch:
            return text

    @admin.display(description=_("وضعیت"), ordering="status")
    def status_badge(self, obj):
        colors = {
            PaymentStatus.CREATED: "#6c757d",
            PaymentStatus.AUTHORIZED: "#17a2b8",
            PaymentStatus.AWAITING_MERCHANT_CONFIRMATION: "#0dcaf0",
            PaymentStatus.COMPLETED: "#28a745",
            PaymentStatus.CANCELLED: "#dc3545",
            PaymentStatus.EXPIRED: "#fd7e14",
            PaymentStatus.FAILED: "#dc3545",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.display(description=_("مبلغ"), ordering="amount")
    def amount_display(self, obj):
        return format_html(
            '<span style="direction:ltr;">{}</span>',
            format(int(obj.amount or 0), ",d"),
        )

    @admin.display(description=_("درخواست پرداخت"), ordering="payment_request")
    def payment_request_link(self, obj):
        if not obj.payment_request_id:
            return "-"
        return self._admin_change_link(
            obj.payment_request._meta.app_label,
            obj.payment_request._meta.model_name,
            obj.payment_request_id,
            obj.payment_request.reference_code,
        )

    @admin.display(description=_("پرداخت‌کننده"), ordering="payer")
    def payer_link(self, obj):
        if not obj.payer_id:
            return "-"
        return self._admin_change_link(
            obj.payer._meta.app_label,
            obj.payer._meta.model_name,
            obj.payer_id,
            obj.payer.username,
        )

    @admin.display(description=_("کیف پول"), ordering="payer_wallet")
    def payer_wallet_link(self, obj):
        if not obj.payer_wallet_id:
            return "-"
        return self._admin_change_link(
            obj.payer_wallet._meta.app_label,
            obj.payer_wallet._meta.model_name,
            obj.payer_wallet_id,
            obj.payer_wallet.wallet_number,
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
