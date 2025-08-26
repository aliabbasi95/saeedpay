# credit/admin/credit_limit.py

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from credit.models import CreditLimit
from credit.utils.choices import CreditLimitStatus


class PendingApprovalFilter(admin.SimpleListFilter):
    title = _('وضعیت تایید')
    parameter_name = 'approval_status'

    def lookups(self, request, model_admin):
        return (
            ('pending', _('در انتظار تایید')),
            ('approved', _('تایید شده')),
            ('rejected', _('رد شده')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'pending':
            return queryset.filter(status=CreditLimitStatus.PENDING)
        elif self.value() == 'approved':
            return queryset.filter(status=CreditLimitStatus.ACTIVE)
        elif self.value() == 'rejected':
            return queryset.filter(status__in=[CreditLimitStatus.EXPIRED, CreditLimitStatus.SUSPENDED])
        return queryset


@admin.register(CreditLimit)
class CreditLimitAdmin(admin.ModelAdmin):
    list_display = [
        "reference_code",
        "user",
        "approved_limit_display",
        "available_limit_display",
        "used_limit_display",
        "status_display",
        "expiry_date",
        "approved_at",
        "created_at",
    ]

    list_filter = [
        PendingApprovalFilter,
        "status",
        "expiry_date", 
        "created_at",
        "approved_at",
        ("user", admin.RelatedOnlyFieldListFilter),
    ]

    search_fields = [
        "reference_code",
        "user__username",
        "user__first_name",
        "user__last_name",
    ]

    readonly_fields = [
        "reference_code", 
        "created_at", 
        "updated_at",
        "available_limit_display",
        "approved_at",
    ]

    fieldsets = (
        (_("اطلاعات کاربر"), {"fields": ("user",)}),
        (
            _("محدودیت اعتباری"),
            {
                "fields": (
                    "approved_limit",
                    "available_limit_display",
                    "used_limit",
                )
            },
        ),
        (
            _("وضعیت و اعتبار"),
            {
                "fields": (
                    "status",
                    "expiry_date",
                    "approved_at",
                    "grace_period_days",
                )
            },
        ),
        (
            _("اطلاعات پیگیری"),
            {
                "fields": (
                    "reference_code",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    actions = ["approve_credit_limits", "reject_credit_limits"]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def approved_limit_display(self, obj):
        """Display approved limit with formatting"""
        return f"{obj.approved_limit:,} ریال"
    approved_limit_display.short_description = _("حد اعتباری تایید شده")
    
    def available_limit_display(self, obj):
        """Display available limit with formatting"""
        if obj.approved_limit is None:
            return "-"
        return f"{obj.available_limit:,} ریال"
    available_limit_display.short_description = _("اعتبار موجود")
    
    def used_limit_display(self, obj):
        """Display used limit with formatting"""
        return f"{obj.used_limit:,} ریال"
    used_limit_display.short_description = _("اعتبار استفاده شده")
    
    def status_display(self, obj):
        """Display status with color coding"""
        colors = {
            CreditLimitStatus.PENDING: '#ffc107',  # yellow
            CreditLimitStatus.ACTIVE: '#28a745',   # green
            CreditLimitStatus.SUSPENDED: '#6c757d', # gray
            CreditLimitStatus.EXPIRED: '#dc3545',   # red
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = _("وضعیت")
    
    def approve_credit_limits(self, request, queryset):
        """Admin action to approve pending credit limits"""
        pending_limits = queryset.filter(status=CreditLimitStatus.PENDING)
        
        if not pending_limits.exists():
            self.message_user(
                request,
                _("هیچ حد اعتباری در انتظار تایید انتخاب نشده است."),
                messages.WARNING
            )
            return
        
        approved_count = 0
        failed_count = 0
        
        for credit_limit in pending_limits:
            try:
                credit_limit.approve_and_activate()
                approved_count += 1
            except Exception as e:
                failed_count += 1
                self.message_user(
                    request,
                    _(f"خطا در تایید حد اعتباری {credit_limit.reference_code}: {str(e)}"),
                    messages.ERROR
                )
        
        if approved_count > 0:
            self.message_user(
                request,
                _(f"{approved_count} حد اعتباری با موفقیت تایید و فعال شد."),
                messages.SUCCESS
            )
        
        if failed_count > 0:
            self.message_user(
                request,
                _(f"{failed_count} حد اعتباری تایید نشد."),
                messages.ERROR
            )
    
    approve_credit_limits.short_description = _("تایید و فعال‌سازی حدود اعتباری انتخاب شده")
    
    def reject_credit_limits(self, request, queryset):
        """Admin action to reject pending credit limits"""
        pending_limits = queryset.filter(status=CreditLimitStatus.PENDING)
        
        if not pending_limits.exists():
            self.message_user(
                request,
                _("هیچ حد اعتباری در انتظار تایید انتخاب نشده است."),
                messages.WARNING
            )
            return
        
        rejected_count = 0
        failed_count = 0
        
        for credit_limit in pending_limits:
            try:
                credit_limit.reject("رد شده توسط مدیر")
                rejected_count += 1
            except Exception as e:
                failed_count += 1
                self.message_user(
                    request,
                    _(f"خطا در رد حد اعتباری {credit_limit.reference_code}: {str(e)}"),
                    messages.ERROR
                )
        
        if rejected_count > 0:
            self.message_user(
                request,
                _(f"{rejected_count} حد اعتباری رد شد."),
                messages.SUCCESS
            )
        
        if failed_count > 0:
            self.message_user(
                request,
                _(f"{failed_count} حد اعتباری رد نشد."),
                messages.ERROR
            )
    
    reject_credit_limits.short_description = _("رد حدود اعتباری انتخاب شده")
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        # Allow viewing but restrict editing based on status
        if obj and obj.status == CreditLimitStatus.ACTIVE:
            # Only allow changing certain fields for active credit limits
            return request.user.is_superuser
        return super().has_change_permission(request, obj)
