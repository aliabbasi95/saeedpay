# wallets/admin/transfer.py

from django.contrib import admin, messages
from django.urls import reverse, NoReverseMatch
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from lib.erp_base.admin import BaseAdmin
from wallets.models import WalletTransferRequest
from wallets.utils.choices import TransferStatus


@admin.register(WalletTransferRequest)
class WalletTransferRequestAdmin(BaseAdmin):
    list_display = (
        "reference_code",
        "status_badge",
        "amount_display",
        "sender_wallet_link",
        "receiver_target",
        "transaction_link",
        "expires_at",
        "jalali_creation_time",
    )
    list_filter = ("status", "created_at", "expires_at")
    search_fields = (
        "reference_code",
        "description",
        "sender_wallet__wallet_number",
        "receiver_wallet__wallet_number",
        "receiver_phone_number",
    )
    readonly_fields = (
        "reference_code",
        "status",
        "amount",
        "description",
        "sender_wallet",
        "receiver_wallet",
        "receiver_phone_number",
        "transaction",
        "expires_at",
        "jalali_creation_time",
        "jalali_update_time",
    )
    fieldsets = (
        (_("Identifiers"), {"fields": ("reference_code",)}),
        (_("Status & Amount"), {"fields": ("status", "amount")}),
        (_("Route / Target"), {
            "fields": ("sender_wallet", "receiver_wallet",
                       "receiver_phone_number")
        }),
        (_("Relations"), {"fields": ("transaction",)}),
        (_("Timeline"), {
            "fields": ("expires_at", "jalali_creation_time",
                       "jalali_update_time")
        }),
    )
    list_select_related = ("sender_wallet", "receiver_wallet", "transaction")
    autocomplete_fields = ("sender_wallet", "receiver_wallet", "transaction")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    actions = ("mark_rejected_action", "mark_expired_action")

    # -------- helpers --------
    def _change_link(self, app_label, model_name, pk, text):
        try:
            url = reverse(f"admin:{app_label}_{model_name}_change", args=[pk])
            return format_html('<a href="{}">{}</a>', url, text)
        except NoReverseMatch:
            return text

    @admin.display(description=_("Status"), ordering="status")
    def status_badge(self, obj: WalletTransferRequest):
        colors = {
            TransferStatus.PENDING_CONFIRMATION: "#17a2b8",
            TransferStatus.SUCCESS: "#28a745",
            TransferStatus.REJECTED: "#dc3545",
            TransferStatus.EXPIRED: "#fd7e14",
        }
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            colors.get(obj.status, "#6c757d"),
            obj.get_status_display()
        )

    @admin.display(description=_("Amount"), ordering="amount")
    def amount_display(self, obj: WalletTransferRequest):
        txt = format(int(obj.amount or 0), ",d")
        return format_html('<span style="direction:ltr;">{}</span>', txt)

    @admin.display(description=_("Sender"), ordering="sender_wallet")
    def sender_wallet_link(self, obj: WalletTransferRequest):
        if not obj.sender_wallet_id:
            return "-"
        label = getattr(
            obj.sender_wallet, "wallet_number", f"#{obj.sender_wallet_id}"
        )
        return self._change_link(
            "wallets", "wallet", obj.sender_wallet_id, label
        )

    @admin.display(
        description=_("Receiver / Phone"), ordering="receiver_wallet"
    )
    def receiver_target(self, obj: WalletTransferRequest):
        if obj.receiver_wallet_id:
            label = getattr(
                obj.receiver_wallet, "wallet_number",
                f"#{obj.receiver_wallet_id}"
            )
            return self._change_link(
                "wallets", "wallet", obj.receiver_wallet_id, label
            )
        return obj.receiver_phone_number or "-"

    @admin.display(description=_("Transaction"))
    def transaction_link(self, obj: WalletTransferRequest):
        if not obj.transaction_id:
            return "-"
        label = getattr(
            obj.transaction, "reference_code", f"#{obj.transaction_id}"
        )
        return self._change_link(
            "wallets", "transaction", obj.transaction_id, label
        )

    # -------- actions (safe, بدون تایید مالی) --------
    def _apply_action(self, request, queryset, target_status, invalid_from):
        done, failed = 0, 0
        for tr in queryset:
            if tr.status in invalid_from:
                failed += 1
                continue
            try:
                tr.status = target_status
                tr.save(update_fields=["status"])
                done += 1
            except Exception as e:
                failed += 1
                self.message_user(
                    request, f"{tr.reference_code}: {e}", level=messages.ERROR
                )
        if done:
            self.message_user(
                request, _("{done} updated.").format(done=done),
                level=messages.SUCCESS
            )
        if failed:
            self.message_user(
                request, _("{failed} skipped.").format(failed=failed),
                level=messages.WARNING
            )

    @admin.action(description=_("Mark as Rejected"))
    def mark_rejected_action(self, request, queryset):
        self._apply_action(
            request, queryset, TransferStatus.REJECTED,
            invalid_from={TransferStatus.SUCCESS, TransferStatus.REJECTED,
                          TransferStatus.EXPIRED},
        )

    @admin.action(description=_("Mark as Expired"))
    def mark_expired_action(self, request, queryset):
        self._apply_action(
            request, queryset, TransferStatus.EXPIRED,
            invalid_from={TransferStatus.SUCCESS, TransferStatus.EXPIRED},
        )

    # -------- perms --------
    def has_add_permission(self, request):  # created by app logic
        return False

    def has_change_permission(self, request, obj=None):  # read-only fields
        return False

    def has_delete_permission(self, request, obj=None):
        return False
