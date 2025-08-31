# wallets/admin/wallet.py

from django.contrib import admin
from django.urls import reverse, NoReverseMatch
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from lib.erp_base.admin import BaseAdmin
from wallets.models import Wallet


@admin.register(Wallet)
class WalletAdmin(BaseAdmin):
    list_display = (
        "wallet_number",
        "user_link",
        "owner_type",
        "kind",
        "balance_display",
        "reserved_balance_display",
        "available_balance_display",
        "jalali_creation_time",
    )
    list_filter = ("owner_type", "kind", "created_at")
    search_fields = ("wallet_number", "user__username", "user__first_name",
                     "user__last_name")
    readonly_fields = (
        "wallet_number",
        "balance",
        "reserved_balance",
        "available_balance_display",
        "jalali_creation_time",
        "jalali_update_time",
    )
    fieldsets = (
        (_("شناسه"), {"fields": ("wallet_number",)}),
        (_("مالک"), {"fields": ("user", "owner_type")}),
        (_("نوع"), {"fields": ("kind",)}),
        (_("مبالغ"), {
            "fields": (
                "balance",
                "reserved_balance",
                "available_balance_display"
            )
        }),
        (_("زمان‌بندی"), {
            "fields": (
                "jalali_creation_time",
                "jalali_update_time"
            )
        }),
    )
    list_select_related = ("user",)
    autocomplete_fields = ("user",)
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    # ---------- display helpers ----------
    def _change_link(self, app_label, model_name, pk, text):
        try:
            url = reverse(f"admin:{app_label}_{model_name}_change", args=[pk])
            return format_html('<a href="{}">{}</a>', url, text)
        except NoReverseMatch:
            return text

    @admin.display(description=_("کاربر"), ordering="user")
    def user_link(self, obj: Wallet):
        if not obj.user_id:
            return "-"
        text = getattr(obj.user, "username", f"#{obj.user_id}")
        return self._change_link("auth", "user", obj.user_id, text)

    @admin.display(description=_("موجودی"), ordering="balance")
    def balance_display(self, obj: Wallet):
        txt = format(int(obj.balance or 0), ",d")
        return format_html('<span style="direction:ltr;">{}</span>', txt)

    @admin.display(description=_("رزرو"), ordering="reserved_balance")
    def reserved_balance_display(self, obj: Wallet):
        txt = format(int(obj.reserved_balance or 0), ",d")
        return format_html('<span style="direction:ltr;">{}</span>', txt)

    @admin.display(description=_("قابل برداشت"))
    def available_balance_display(self, obj: Wallet):
        txt = format(int(obj.available_balance or 0), ",d")
        return format_html('<span style="direction:ltr;">{}</span>', txt)

    # ---------- permissions ----------
    def has_delete_permission(self, request, obj=None):
        return False
