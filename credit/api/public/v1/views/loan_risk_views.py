# credit/api/public/v1/views/loan_risk_views.py

from drf_spectacular.utils import extend_schema_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated

from credit.models import LoanRiskReport
from credit.utils.choices import LoanReportStatus
from credit.api.public.v1.serializers.loan_risk_serializers import (
    LoanRiskOTPRequestSerializer,
    LoanRiskOTPVerifySerializer,
    LoanRiskReportSerializer,
    LoanRiskReportDetailSerializer,
    LoanRiskReportListSerializer,
)
from credit.api.public.v1.schema import (
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


@loan_risk_otp_request_schema
class LoanRiskOTPRequestView(APIView):
    """
    Request OTP for loan risk validation (Stage 1).
    
    Sends an OTP to user's registered mobile number to start the loan validation process.
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = LoanRiskOTPRequestSerializer
    
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        profile = serializer.validated_data['_profile']

        # Create a new report record and send OTP
        report = LoanRiskReport.objects.create(
            profile=profile,
            national_code=profile.national_id,
            mobile_number=profile.phone_number,
        )

        task_result = send_loan_validation_otp.delay(report.id)

        return Response(
            {
                "success": True,
                "message": "درخواست ارسال کد با موفقیت ثبت شد. کد به زودی به شماره موبایل شما ارسال خواهد شد.",
                "report_id": report.id,
                "task_id": task_result.id,
            },
            status=status.HTTP_200_OK,
        )


@loan_risk_otp_verify_schema
class LoanRiskOTPVerifyView(APIView):
    """
    Verify OTP and request loan risk report (Stage 2).
    
    Verifies the OTP code and initiates the credit report generation.
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = LoanRiskOTPVerifySerializer
    
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


@loan_risk_report_check_schema
class LoanRiskReportCheckView(APIView):
    """
    Manually check loan risk report status (Stage 3).
    
    Check if the credit report is ready and retrieve it if available.
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = LoanRiskReportSerializer  
    
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
        if report.status == LoanReportStatus.COMPLETED:
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


@loan_risk_report_detail_schema
class LoanRiskReportDetailView(generics.RetrieveAPIView):
    """
    Retrieve detailed loan risk report including full JSON data.
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = LoanRiskReportDetailSerializer
    
    def get_queryset(self):
        profile = Profile.objects.get(user=self.request.user)
        return LoanRiskReport.objects.filter(profile=profile)


@loan_risk_report_list_schema
class LoanRiskReportListView(generics.ListAPIView):
    """
    List all loan risk reports for the authenticated user.
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = LoanRiskReportListSerializer
    
    def get_queryset(self):
        profile = Profile.objects.get(user=self.request.user)
        return LoanRiskReport.objects.filter(profile=profile).order_by('-created_at')


@loan_risk_report_latest_schema
class LoanRiskReportLatestView(APIView):
    """
    Get the latest loan risk report for the authenticated user.
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = LoanRiskReportSerializer  
    
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
