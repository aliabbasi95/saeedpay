# wallets/admin/transaction.py

from django.contrib import admin
from django.urls import reverse, NoReverseMatch
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from lib.erp_base.admin import BaseAdmin
from wallets.models import Transaction
from wallets.utils.choices import TransactionStatus


@admin.register(Transaction)
class TransactionAdmin(BaseAdmin):
    list_display = (
        "reference_code",
        "status_badge",
        "amount_display",
        "from_wallet_link",
        "to_wallet_link",
        "payment_request_link",
        "jalali_creation_time",
    )
    list_filter = ("status", "created_at")
    search_fields = (
        "reference_code",
        "description",
        "from_wallet__id",
        "to_wallet__id",
        "from_wallet__user__username",
        "from_wallet__user__first_name",
        "from_wallet__user__last_name",
        "to_wallet__user__username",
        "to_wallet__user__first_name",
        "to_wallet__user__last_name",
        "payment_request__reference_code",
    )
    readonly_fields = (
        "reference_code",
        "status",
        "from_wallet",
        "to_wallet",
        "amount",
        "payment_request",
        "description",
        "jalali_creation_time",
        "jalali_update_time",
    )
    fieldsets = (
        (_("اطلاعات پیگیری"), {"fields": ("reference_code",)}),
        (_("جزئیات تراکنش"),
         {"fields": ("status", "amount", "description")}),
        (_("مسیر انتقال"),
         {"fields": ("from_wallet", "to_wallet")}),
        (_("ارتباطات"),
         {"fields": ("payment_request",)}),
        (_("زمان‌بندی"),
         {"fields": ("jalali_creation_time", "jalali_update_time")}),
    )
    list_select_related = ("from_wallet", "to_wallet", "payment_request")
    autocomplete_fields = ("from_wallet", "to_wallet", "payment_request")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    # -------- display helpers --------
    def status_badge(self, obj: Transaction):
        colors = {
            TransactionStatus.PENDING: "#ffc107",  # yellow
            TransactionStatus.SUCCESS: "#28a745",  # green
            TransactionStatus.FAILED: "#dc3545",  # red
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            color,
            obj.get_status_display()
        )

    status_badge.short_description = _("وضعیت")

    def amount_display(self, obj: Transaction):
        return format_html(
            '<span style="direction:ltr;">{:,.0f}</span>', obj.amount
        )

    amount_display.short_description = _("مبلغ")

    def _admin_change_link(self, app_label, model_name, pk, text=None):
        try:
            url = reverse(f"admin:{app_label}_{model_name}_change", args=[pk])
            return format_html('<a href="{}">{}</a>', url, text or pk)
        except NoReverseMatch:
            return text or str(pk)

    def from_wallet_link(self, obj: Transaction):
        label = getattr(obj.from_wallet, "id", "-")
        return self._admin_change_link(
            "wallets", "wallet", obj.from_wallet_id, text=f"#{label}"
        )

    from_wallet_link.short_description = _("از کیف پول")

    def to_wallet_link(self, obj: Transaction):
        label = getattr(obj.to_wallet, "id", "-")
        return self._admin_change_link(
            "wallets", "wallet", obj.to_wallet_id, text=f"#{label}"
        )

    to_wallet_link.short_description = _("به کیف پول")

    def payment_request_link(self, obj: Transaction):
        if not obj.payment_request_id:
            return "-"
        label = getattr(
            obj.payment_request, "reference_code", f"#{obj.payment_request_id}"
        )
        return self._admin_change_link(
            "wallets", "paymentrequest", obj.payment_request_id, text=label
        )

    payment_request_link.short_description = _("درخواست پرداخت")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
