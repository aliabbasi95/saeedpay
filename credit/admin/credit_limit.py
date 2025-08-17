# credit/admin/credit_limit.py

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from credit.models import CreditLimit


@admin.register(CreditLimit)
class CreditLimitAdmin(admin.ModelAdmin):
    list_display = [
        'reference_code',
        'user',
        'approved_limit',
        'available_limit',
        'used_limit',
        'status',
        'expiry_date',
        'created_at'
    ]
    
    list_filter = [
        'status',
        'expiry_date',
        'created_at'
    ]
    
    search_fields = [
        'reference_code',
        'user__username',
        'user__first_name',
        'user__last_name'
    ]
    
    readonly_fields = [
        'reference_code',
        'created_at',
        'updated_at'
    ]
    
    fieldsets = (
        (_('اطلاعات کاربر'), {
            'fields': ('user',)
        }),
        (_('محدودیت اعتباری'), {
            'fields': (
                'approved_limit',
                'available_limit',
                'used_limit',
            )
        }),
        (_('وضعیت و اعتبار'), {
            'fields': (
                'status',
                'expiry_date',
                'approved_at',
            )
        }),
        (_('اطلاعات پیگیری'), {
            'fields': (
                'reference_code',
                'created_at',
                'updated_at',
            )
        }),
    )
    
    def has_delete_permission(self, request, obj=None):
        return False
