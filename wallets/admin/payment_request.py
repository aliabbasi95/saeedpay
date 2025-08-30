# wallets/admin/payment_request.py

from django.contrib import admin, messages
from django.urls import reverse, NoReverseMatch
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
        "amount_display",
        "store_link",
        "paid_by_link",
        "paid_wallet_link",
        "expires_at",
        "paid_at",
        "jalali_creation_time",
    )
    list_filter = ("status", "store", "created_at", "expires_at")
    search_fields = (
        "reference_code",
        "description",
        "store__name",
        "paid_by__username",
        "paid_by__first_name",
        "paid_by__last_name",
        "paid_wallet__wallet_number",
    )
    readonly_fields = (
        "reference_code",
        "status",
        "amount",
        "description",
        "return_url",
        "store",
        "paid_by",
        "paid_wallet",
        "expires_at",
        "paid_at",
        "jalali_creation_time",
        "jalali_update_time",
    )
    fieldsets = (
        (_("شناسه"), {"fields": ("reference_code",)}),
        (_("جزئیات"),
         {"fields": ("status", "amount", "description", "return_url")}),
        (_("ارتباطات"),
         {"fields": ("store", "paid_by", "paid_wallet")}),
        (_("زمان‌بندی"),
         {
             "fields": (
                 "expires_at",
                 "paid_at",
                 "jalali_creation_time",
                 "jalali_update_time"
             )
         }),
    )
    list_select_related = ("store", "paid_by", "paid_wallet")
    autocomplete_fields = ("store", "paid_by", "paid_wallet")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    actions = (
        "mark_completed_action",
        "mark_cancelled_action",
        "mark_expired_action"
    )

    # ---------- display helpers ----------
    def _change_link(self, app_label, model_name, pk, text):
        try:
            url = reverse(f"admin:{app_label}_{model_name}_change", args=[pk])
            return format_html('<a href="{}">{}</a>', url, text)
        except NoReverseMatch:
            return text

    def amount_display(self, obj: PaymentRequest):
        return format_html(
            '<span style="direction:ltr;">{:,.0f}</span>', obj.amount
        )

    amount_display.short_description = _("مبلغ")

    def status_badge(self, obj: PaymentRequest):
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
            color, obj.get_status_display()
        )

    status_badge.short_description = _("وضعیت")

    def store_link(self, obj: PaymentRequest):
        if not obj.store_id:
            return "-"
        name = getattr(obj.store, "name", f"#{obj.store_id}")
        return self._change_link("store", "store", obj.store_id, name)

    store_link.short_description = _("فروشگاه")

    def paid_by_link(self, obj: PaymentRequest):
        if not obj.paid_by_id:
            return "-"
        text = getattr(obj.paid_by, "username", f"#{obj.paid_by_id}")
        return self._change_link("auth", "user", obj.paid_by_id, text)

    paid_by_link.short_description = _("پرداخت‌کننده")

    def paid_wallet_link(self, obj: PaymentRequest):
        if not obj.paid_wallet_id:
            return "-"
        label = getattr(
            obj.paid_wallet, "wallet_number", f"#{obj.paid_wallet_id}"
        )
        return self._change_link(
            "wallets", "wallet", obj.paid_wallet_id, label
        )

    paid_wallet_link.short_description = _("کیف پول پرداخت‌کننده")

    # ---------- actions ----------
    def _apply_action(
            self, request, queryset, method_name, success_msg,
            invalid_states=None
    ):
        done = 0
        failed = 0
        invalid_states = set(invalid_states or ())
        for pr in queryset:
            # اگر وضعیت فعلی اجازه این اکشن را نمی‌دهد، عبور کن
            if pr.status in invalid_states:
                failed += 1
                continue
            try:
                getattr(pr, method_name)()
                done += 1
            except Exception as e:
                failed += 1
                self.message_user(
                    request, f"{pr.reference_code}: {e}", level=messages.ERROR
                )
        if done:
            self.message_user(
                request, success_msg.format(done=done), level=messages.SUCCESS
            )
        if failed:
            self.message_user(
                request, _(f"{failed} مورد اعمال نشد."), level=messages.WARNING
            )

    @admin.action(description=_("علامت‌گذاری به عنوان تکمیل‌شده"))
    def mark_completed_action(self, request, queryset):
        # Completed دوباره قابل تغییر نیست
        self._apply_action(
            request, queryset, "mark_completed",
            success_msg=_("{done} مورد تکمیل شد."),
            invalid_states={PaymentRequestStatus.COMPLETED,
                            PaymentRequestStatus.CANCELLED,
                            PaymentRequestStatus.EXPIRED},
        )

    @admin.action(description=_("لغو کردن درخواست‌ها"))
    def mark_cancelled_action(self, request, queryset):
        self._apply_action(
            request, queryset, "mark_cancelled",
            success_msg=_("{done} مورد لغو شد."),
            invalid_states={PaymentRequestStatus.CANCELLED,
                            PaymentRequestStatus.EXPIRED},
        )

    @admin.action(description=_("منقضی کردن درخواست‌ها"))
    def mark_expired_action(self, request, queryset):
        self._apply_action(
            request, queryset, "mark_expired",
            success_msg=_("{done} مورد منقضی شد."),
            invalid_states={PaymentRequestStatus.EXPIRED},
        )

    # ---------- permissions ----------
    def has_add_permission(self, request):
        return False  # ایجاد دستی درخواست پرداخت از ادمین ممنوع

    def has_change_permission(self, request, obj=None):
        return False  # ویرایشِ دستی نیز ممنوع؛ فقط اکشن‌های دامینی بالا مجازند

    def has_delete_permission(self, request, obj=None):
        return False
