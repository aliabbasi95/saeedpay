# wallets/admin/payment_event.py

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from lib.erp_base.admin import BaseAdmin
from wallets.models import PaymentEvent


@admin.register(PaymentEvent)
class PaymentEventAdmin(BaseAdmin):
    list_display = (
        "id",
        "event_type",
        "payment_request",
        "payment",
        "actor",
        "from_status",
        "to_status",
        "jalali_creation_time",
    )
    list_filter = ("event_type", "from_status", "to_status", "created_at")
    search_fields = (
        "payment_request__reference_code",
        "payment__reference_code",
        "actor__username",
        "description",
    )
    readonly_fields = (
        "payment_request",
        "payment",
        "transaction",
        "actor",
        "event_type",
        "from_status",
        "to_status",
        "description",
        "extra_data",
        "jalali_creation_time",
        "jalali_update_time",
    )
    ordering = ("-created_at", "-id")

    fieldsets = (
        (
            _("اطلاعات اصلی"),
            {
                "fields": (
                    "payment_request",
                    "payment",
                    "transaction",
                    "actor",
                    "event_type",
                )
            },
        ),
        (
            _("تغییر وضعیت"),
            {
                "fields": (
                    "from_status",
                    "to_status",
                    "description",
                    "extra_data",
                )
            },
        ),
        (
            _("زمان"),
            {
                "fields": (
                    "jalali_creation_time",
                    "jalali_update_time",
                )
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
