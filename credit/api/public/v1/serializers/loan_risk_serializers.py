# credit/api/public/v1/serializers/loan_risk_serializers.py

from rest_framework import serializers
from credit.models import LoanRiskReport
from profiles.models.profile import Profile
from profiles.utils.choices import AuthenticationStage


class LoanRiskOTPRequestSerializer(serializers.Serializer):
    """Serializer for requesting OTP for loan validation."""
    
    def validate(self, data):
        """Validate that user has a profile with required fields and correct auth stage."""
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError(
                {"non_field_errors": ["کاربر احراز هویت نشده است."]}
            )
        
        try:
            profile = Profile.objects.get(user=request.user)
        except Profile.DoesNotExist:
            raise serializers.ValidationError(
                {"non_field_errors": ["پروفایل کاربری یافت نشد."]}
            )
        
        # Check auth stage - must be IDENTITY_VERIFIED (Stage 3)
        if profile.auth_stage != AuthenticationStage.IDENTITY_VERIFIED:
            raise serializers.ValidationError(
                {"non_field_errors": [
                    "شما باید ابتدا مرحله احراز هویت (تطبیق کد ملی و شماره موبایل) را تکمیل کنید."
                ]}
            )
        
        if not profile.national_id:
            raise serializers.ValidationError(
                {"non_field_errors": ["کد ملی در پروفایل شما ثبت نشده است."]}
            )
        
        if not profile.phone_number:
            raise serializers.ValidationError(
                {"non_field_errors": ["شماره موبایل در پروفایل شما ثبت نشده است."]}
            )
        
        # Check cooldown period (30 days between reports)
        can_request, reason, last_report = LoanRiskReport.can_user_request_new_report(profile)
        if not can_request:
            last_report_date = last_report.completed_at.strftime('%Y/%m/%d') if last_report else ''
            raise serializers.ValidationError(
                {"non_field_errors": [
                    f"شما قبلاً در تاریخ {last_report_date} گزارش اعتبارسنجی دریافت کرده‌اید. "
                    f"برای درخواست گزارش جدید {reason}."
                ]}
            )
        
        # Store profile and last report in validated data
        data['_profile'] = profile
        data['_last_report'] = last_report
        return data


class LoanRiskOTPVerifySerializer(serializers.Serializer):
    """Serializer for verifying OTP and requesting loan risk report."""
    
    report_id = serializers.IntegerField(required=True)
    otp_code = serializers.CharField(required=True, min_length=4, max_length=10)
    
    def validate_report_id(self, value):
        """Validate that report exists and belongs to current user."""
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("کاربر احراز هویت نشده است.")
        
        try:
            profile = Profile.objects.get(user=request.user)
            report = LoanRiskReport.objects.get(id=value, profile=profile)
        except Profile.DoesNotExist:
            raise serializers.ValidationError("پروفایل کاربری یافت نشد.")
        except LoanRiskReport.DoesNotExist:
            raise serializers.ValidationError("گزارش یافت نشد یا متعلق به شما نیست.")
        
        # Check if report can accept OTP
        if not report.can_request_report():
            raise serializers.ValidationError(
                "گزارش در وضعیت مناسب برای ارسال کد نیست یا کد منقضی شده است."
            )
        
        return value
    
    def validate_otp_code(self, value):
        """Validate OTP code format."""
        if not value.isdigit():
            raise serializers.ValidationError("کد باید فقط شامل اعداد باشد.")
        return value


class LoanRiskReportSerializer(serializers.ModelSerializer):
    """Serializer for LoanRiskReport model."""
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    risk_level_display = serializers.CharField(source='get_risk_level_display', read_only=True)
    is_low_risk = serializers.BooleanField(read_only=True)
    is_medium_risk = serializers.BooleanField(read_only=True)
    is_high_risk = serializers.BooleanField(read_only=True)
    can_request_report = serializers.BooleanField(read_only=True)
    can_check_result = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = LoanRiskReport
        fields = [
            'id',
            'status',
            'status_display',
            'otp_sent_at',
            'report_requested_at',
            'credit_score',
            'risk_level',
            'risk_level_display',
            'grade_description',
            'is_low_risk',
            'is_medium_risk',
            'is_high_risk',
            'report_timestamp',
            'report_types',
            'error_message',
            'error_code',
            'created_at',
            'updated_at',
            'completed_at',
            'can_request_report',
            'can_check_result',
        ]
        read_only_fields = fields


class LoanRiskReportDetailSerializer(LoanRiskReportSerializer):
    """Detailed serializer including full report data."""
    
    class Meta(LoanRiskReportSerializer.Meta):
        fields = LoanRiskReportSerializer.Meta.fields + ['report_data']


class LoanRiskReportListSerializer(serializers.ModelSerializer):
    """Simplified serializer for list view."""
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    risk_level_display = serializers.CharField(source='get_risk_level_display', read_only=True)
    
    class Meta:
        model = LoanRiskReport
        fields = [
            'id',
            'status',
            'status_display',
            'credit_score',
            'risk_level',
            'risk_level_display',
            'grade_description',
            'created_at',
            'completed_at',
        ]
        read_only_fields = fields
