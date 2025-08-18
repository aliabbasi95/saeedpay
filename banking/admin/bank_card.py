# banking/admin/bank_card.py

from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from lib.erp_base.admin import BaseAdmin
from .filters import HasShebaFilter
from ..models import BankCard
from ..services import bank_card_service
from ..utils.choices import BankCardStatus


@admin.register(BankCard)
class BankCardAdmin(BaseAdmin):
    list_display = (
        "masked_card",
        "user",
        "bank",
        "status_badge",
        "is_default",
        "is_active",
        "last_used",
        "jalali_creation_date_time",
    )
    list_filter = (
        "status", "is_default", "is_active", "bank", HasShebaFilter,
    )
    search_fields = (
        "card_number",
        "card_holder_name",
        "sheba",
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "bank__name",
    )
    ordering = ("-is_default", "-created_at")
    list_select_related = ("user", "bank")
    date_hierarchy = "created_at"
    autocomplete_fields = ("user", "bank")

    fieldsets = (
        (_("اطلاعات کارت"), {
            "fields": ("user", "bank", "status", "is_active", "is_default"),
        }),
        (_("جزئیات"), {
            "fields": ("card_number", "last4_readonly", "card_holder_name",
                       "sheba", "last_used"),
        }),
    )

    actions = ("action_set_default", "action_soft_delete")

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = (
            "last4_readonly",
            "rejection_reason",
            "last_used",
            "bank",
            "card_holder_name",
            "sheba",
            # "status",
        )

        if obj is None:
            return readonly_fields

        if obj.status == BankCardStatus.VERIFIED:
            return readonly_fields + ("user", "card_number")

        if obj.status == BankCardStatus.PENDING:
            return readonly_fields + ("user", "card_number")

        if obj.status == BankCardStatus.REJECTED:
            return readonly_fields + ("user",)

        return readonly_fields + ("user", "card_number")

    def masked_card(self, obj: BankCard):
        return format_html("**** **** **** <strong>{}</strong>", obj.last4)

    masked_card.short_description = _("شماره کارت")

    def last4_readonly(self, obj: BankCard):
        return obj.last4

    last4_readonly.short_description = _("۴ رقم آخر")

    def status_badge(self, obj: BankCard):
        color_map = {
            BankCardStatus.VERIFIED: "#2e7d32",
            BankCardStatus.REJECTED: "#c62828",
            BankCardStatus.PENDING: "#757575",
        }
        label_map = {
            BankCardStatus.VERIFIED: _("تأیید شده"),
            BankCardStatus.REJECTED: _("رد شده"),
            BankCardStatus.PENDING: _("در حال بررسی"),
        }
        color = color_map.get(obj.status, "#616161")
        label = label_map.get(obj.status, obj.status)
        return format_html(
            '<span style="display:inline-block;padding:2px 8px;border-radius:12px;'
            'color:#fff;background:{};font-size:12px;">{}</span>',
            color, label
        )

    status_badge.short_description = _("وضعیت")

    def action_set_default(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request, _(
                    "برای این عملیات دقیقاً یک کارت را انتخاب کنید."
                ), level=messages.WARNING
            )
            return
        card = queryset.first()
        if card.status != BankCardStatus.VERIFIED:
            self.message_user(
                request, _(
                    "فقط کارت‌های تأیید‌شده می‌توانند پیش‌فرض شوند."
                ), level=messages.ERROR
            )
            return
        # استفاده از سرویس برای رعایت قید یکتا و صفر کردن بقیه کارت‌ها
        bank_card_service.set_as_default(card.user, card.id)
        self.message_user(
            request, _("کارت انتخابی به عنوان پیش‌فرض ثبت شد."),
            level=messages.SUCCESS
        )

    action_set_default.short_description = _("قرار دادن به‌عنوان کارت پیش‌فرض")

    def action_soft_delete(self, request, queryset):
        count = 0
        for card in queryset:
            bank_card_service.soft_delete_card(card)
            count += 1
        self.message_user(
            request, _("%(count)d کارت غیرفعال شد.") % {"count": count},
            level=messages.SUCCESS
        )

    action_soft_delete.short_description = _("حذف نرم (غیرفعال‌سازی)")

    def save_model(self, request, obj, form, change):
        old_status = None
        if change:
            old_status = type(obj).objects.only("status").get(pk=obj.pk).status
        super().save_model(request, obj, form, change)
        bank_card_service.enqueue_validation_if_pending(old_status, obj)
