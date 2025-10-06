# credit/admin/loan_risk_report.py

from django.contrib import admin
from credit.models import LoanRiskReport


@admin.register(LoanRiskReport)
class LoanRiskReportAdmin(admin.ModelAdmin):
    """Admin interface for LoanRiskReport model."""
    
    list_display = [
        'id',
        'profile',
        'national_code',
        'mobile_number',
        'status',
        'credit_score',
        'risk_level',
        'created_at',
        'completed_at',
    ]
    
    list_filter = [
        'status',
        'risk_level',
        'created_at',
        'completed_at',
    ]
    
    search_fields = [
        'profile__user__username',
        'national_code',
        'mobile_number',
        'otp_unique_id',
        'report_unique_id',
    ]
    
    readonly_fields = [
        'profile',
        'national_code',
        'mobile_number',
        'otp_unique_id',
        'otp_sent_at',
        'report_unique_id',
        'report_requested_at',
        'credit_score',
        'risk_level',
        'grade_description',
        'report_data',
        'report_timestamp',
        'report_types',
        'error_message',
        'error_code',
        'created_at',
        'updated_at',
        'completed_at',
    ]
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('profile', 'national_code', 'mobile_number', 'status')
        }),
        ('مرحله 1: ارسال OTP', {
            'fields': ('otp_unique_id', 'otp_sent_at')
        }),
        ('مرحله 2: درخواست گزارش', {
            'fields': ('report_unique_id', 'report_requested_at')
        }),
        ('مرحله 3: نتایج گزارش', {
            'fields': (
                'credit_score',
                'risk_level',
                'grade_description',
                'report_timestamp',
                'report_types',
            )
        }),
        ('داده‌های کامل', {
            'fields': ('report_data',),
            'classes': ('collapse',)
        }),
        ('خطاها', {
            'fields': ('error_message', 'error_code'),
            'classes': ('collapse',)
        }),
        ('تاریخچه', {
            'fields': ('created_at', 'updated_at', 'completed_at')
        }),
    )
    
    def has_add_permission(self, request):
        """Prevent manual creation of reports."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of completed reports."""
        if obj and obj.status == LoanRiskReport.ReportStatus.COMPLETED:
            return False
        return super().has_delete_permission(request, obj)
