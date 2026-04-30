# apps/wallets/admin/transaction.py

from django.contrib import admin
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.wallets.models import Transaction
from apps.wallets.utils.choices import TransactionStatus
from lib.erp_base.admin import BaseAdmin


@admin.register(Transaction)
class TransactionAdmin(BaseAdmin):
    list_display = (
        "reference_code",
        "status_badge",
        "purpose",
        "amount_display",
        "payment_link",
        "from_wallet_link",
        "to_wallet_link",
        "related_transaction_link",
        "jalali_creation_time",
    )
    list_filter = ("status", "purpose", "created_at")
    search_fields = (
        "reference_code",
        "description",
        "payment__reference_code",
        "payment_request__reference_code",
        "from_wallet__wallet_number",
        "to_wallet__wallet_number",
    )
    readonly_fields = (
        "reference_code",
        "status",
        "purpose",
        "payment",
        "related_transaction",
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
        (
            _("جزئیات تراکنش"),
            {
                "fields": (
                    "status",
                    "purpose",
                    "amount",
                    "description",
                )
            },
        ),
        (
            _("ارتباطات"),
            {
                "fields": (
                    "payment",
                    "payment_request",
                    "related_transaction",
                )
            },
        ),
        (_("مسیر انتقال"), {"fields": ("from_wallet", "to_wallet")}),
        (_("زمان‌بندی"), {"fields": ("jalali_creation_time", "jalali_update_time")}),
    )
    list_select_related = (
        "payment",
        "payment_request",
        "related_transaction",
        "from_wallet",
        "to_wallet",
    )
    autocomplete_fields = (
        "payment",
        "payment_request",
        "related_transaction",
        "from_wallet",
        "to_wallet",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    def _admin_change_link(self, app_label, model_name, pk, text=None):
        try:
            url = reverse(f"admin:{app_label}_{model_name}_change", args=[pk])
            return format_html('<a href="{}">{}</a>', url, text or pk)
        except NoReverseMatch:
            return text or str(pk)

    @admin.display(description=_("وضعیت"), ordering="status")
    def status_badge(self, obj):
        colors = {
            TransactionStatus.PENDING: "#ffc107",
            TransactionStatus.SUCCESS: "#28a745",
            TransactionStatus.FAILED: "#dc3545",
            TransactionStatus.REVERSED: "#fd7e14",
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

    @admin.display(description=_("پرداخت"), ordering="payment")
    def payment_link(self, obj):
        if not obj.payment_id:
            return "-"
        return self._admin_change_link(
            "wallets",
            "payment",
            obj.payment_id,
            obj.payment.reference_code,
        )

    @admin.display(description=_("از کیف پول"), ordering="from_wallet")
    def from_wallet_link(self, obj):
        return self._admin_change_link(
            "wallets",
            "wallet",
            obj.from_wallet_id,
            obj.from_wallet.wallet_number,
        )

    @admin.display(description=_("به کیف پول"), ordering="to_wallet")
    def to_wallet_link(self, obj):
        return self._admin_change_link(
            "wallets",
            "wallet",
            obj.to_wallet_id,
            obj.to_wallet.wallet_number,
        )

    @admin.display(description=_("تراکنش مرتبط"), ordering="related_transaction")
    def related_transaction_link(self, obj):
        if not obj.related_transaction_id:
            return "-"
        return self._admin_change_link(
            "wallets",
            "transaction",
            obj.related_transaction_id,
            obj.related_transaction.reference_code,
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
