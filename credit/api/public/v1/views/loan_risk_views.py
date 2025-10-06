# credit/api/public/v1/views/loan_risk_views.py

from drf_spectacular.utils import extend_schema_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated

from credit.models import LoanRiskReport
from credit.api.public.v1.serializers.loan_risk_serializers import (
    LoanRiskOTPRequestSerializer,
    LoanRiskOTPVerifySerializer,
    LoanRiskReportSerializer,
    LoanRiskReportDetailSerializer,
    LoanRiskReportListSerializer,
)
from credit.api.public.v1.views.schema import (
    loan_risk_otp_request_schema,
    loan_risk_otp_verify_schema,
    loan_risk_report_check_schema,
    loan_risk_report_detail_schema,
    loan_risk_report_list_schema,
    loan_risk_report_latest_schema,
)
from credit.tasks_loan_validation import (
    send_loan_validation_otp,
    verify_loan_otp_and_request_report,
    check_loan_report_result,
)
from profiles.models.profile import Profile


class LoanRiskOTPRequestView(APIView):
    """
    Request OTP for loan risk validation (Stage 1).
    
    Sends an OTP to user's registered mobile number to start the loan validation process.
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = LoanRiskOTPRequestSerializer
    
    @loan_risk_otp_request_schema
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        profile = serializer.validated_data['_profile']
        
        # Trigger async task
        task_result = send_loan_validation_otp.delay(profile.id)
        
        return Response(
            {
                "success": True,
                "message": "درخواست ارسال کد با موفقیت ثبت شد. کد به زودی به شماره موبایل شما ارسال خواهد شد.",
                "task_id": task_result.id,
            },
            status=status.HTTP_200_OK,
        )


class LoanRiskOTPVerifyView(APIView):
    """
    Verify OTP and request loan risk report (Stage 2).
    
    Verifies the OTP code and initiates the credit report generation.
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = LoanRiskOTPVerifySerializer
    
    @loan_risk_otp_verify_schema
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        report_id = serializer.validated_data['report_id']
        otp_code = serializer.validated_data['otp_code']
        
        # Trigger async task
        task_result = verify_loan_otp_and_request_report.delay(report_id, otp_code)
        
        return Response(
            {
                "success": True,
                "message": "کد تایید شد. گزارش در حال تولید است...",
                "report_id": report_id,
                "task_id": task_result.id,
            },
            status=status.HTTP_200_OK,
        )


class LoanRiskReportCheckView(APIView):
    """
    Manually check loan risk report status (Stage 3).
    
    Check if the credit report is ready and retrieve it if available.
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = LoanRiskReportSerializer  
    
    @loan_risk_report_check_schema
    def post(self, request, report_id):
        try:
            profile = Profile.objects.get(user=request.user)
            report = LoanRiskReport.objects.get(id=report_id, profile=profile)
        except Profile.DoesNotExist:
            return Response(
                {"success": False, "error": "پروفایل یافت نشد"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except LoanRiskReport.DoesNotExist:
            return Response(
                {"success": False, "error": "گزارش یافت نشد یا متعلق به شما نیست"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        # If already completed, return it
        if report.status == LoanRiskReport.ReportStatus.COMPLETED:
            serializer = LoanRiskReportSerializer(report)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        # If can check result, trigger task
        if report.can_check_result():
            task_result = check_loan_report_result.delay(report_id)
            return Response(
                {
                    "success": True,
                    "message": "درخواست بررسی گزارش ثبت شد",
                    "task_id": task_result.id,
                    "status": report.get_status_display(),
                },
                status=status.HTTP_200_OK,
            )
        
        # Otherwise return current status
        serializer = LoanRiskReportSerializer(report)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LoanRiskReportDetailView(generics.RetrieveAPIView):
    """
    Retrieve detailed loan risk report including full JSON data.
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = LoanRiskReportDetailSerializer
    
    @loan_risk_report_detail_schema
    def get_queryset(self):
        profile = Profile.objects.get(user=self.request.user)
        return LoanRiskReport.objects.filter(profile=profile)


class LoanRiskReportListView(generics.ListAPIView):
    """
    List all loan risk reports for the authenticated user.
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = LoanRiskReportListSerializer
    
    @loan_risk_report_list_schema
    def get_queryset(self):
        profile = Profile.objects.get(user=self.request.user)
        return LoanRiskReport.objects.filter(profile=profile).order_by('-created_at')


class LoanRiskReportLatestView(APIView):
    """
    Get the latest loan risk report for the authenticated user.
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = LoanRiskReportSerializer  
    
    @loan_risk_report_latest_schema
    def get(self, request):
        try:
            profile = Profile.objects.get(user=request.user)
            report = LoanRiskReport.objects.filter(profile=profile).order_by('-created_at').first()
            
            if not report:
                return Response(
                    {"error": "هیچ گزارشی یافت نشد"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            serializer = LoanRiskReportSerializer(report)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Profile.DoesNotExist:
            return Response(
                {"error": "پروفایل یافت نشد"},
                status=status.HTTP_404_NOT_FOUND,
            )
