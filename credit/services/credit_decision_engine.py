# credit/services/credit_decision_engine.py

from datetime import timedelta
from typing import Dict, Any
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from credit.utils.constants import CREDIT_LIMIT_DEFAULT_EXPIRY_DAYS

from credit.models import CreditLimit
from credit.utils.risk_scoring import RiskScoringEngine


class CreditDecisionEngine:
    """
    Engine for making credit decisions based on user profile, KYC data, and risk factors
    """
    
    def __init__(self):
        self.risk_engine = RiskScoringEngine()
    
    def evaluate_credit_application(
        self,
        user,
        requested_amount: int,
        kyc_data: Dict[str, Any] = None,
        income_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Evaluate credit application and make decision
        
        Args:
            user: Django user instance
            requested_amount: Requested credit amount in Rials
            kyc_data: KYC verification data
            income_data: Income verification data
            
        Returns:
            Dict with decision details
        """
        
        # Calculate risk score
        risk_score = self.risk_engine.calculate_score(user, kyc_data, income_data)
        
        # Determine approved limit based on risk score
        approved_limit = self._determine_credit_limit(risk_score, income_data)
        
        # Make decision
        decision = self._make_decision(risk_score, requested_amount, approved_limit)
        
        # Create credit limit if approved
        if decision['status'] == 'approved':
            credit_limit = self._create_credit_limit(user, approved_limit)
            decision['credit_limit_id'] = credit_limit.id
            
            # Create initial statement for the user
            from credit.models.statement import Statement
            Statement.objects.create_initial_statement(user)
        
        return decision
    
    def _determine_credit_limit(self, risk_score: int, income_data: Dict[str, Any]) -> int:
        """Determine credit limit based on risk score and income"""
        
        # Base limit calculation
        base_limit = 0
        
        if income_data and 'monthly_income' in income_data:
            monthly_income = income_data['monthly_income']
            # Limit is 3-6 months of income based on risk score
            multiplier = max(1, min(6, (risk_score / 20)))  # 1-6 months
            base_limit = int(monthly_income * multiplier)
        else:
            # Default limits based on risk score
            if risk_score >= 80:
                base_limit = 50_000_000  # 5M Toman
            elif risk_score >= 60:
                base_limit = 30_000_000  # 3M Toman
            elif risk_score >= 40:
                base_limit = 15_000_000  # 1.5M Toman
            else:
                base_limit = 5_000_000   # 500K Toman
        
        # Apply risk score multiplier
        risk_multiplier = risk_score / 100.0
        final_limit = int(base_limit * risk_multiplier)
        
        # Ensure minimum limit
        return max(1_000_000, final_limit)  # Minimum 100K Toman
    
    def _make_decision(self, risk_score: int, requested_amount: int, approved_limit: int) -> Dict[str, Any]:
        """Make final credit decision"""
        
        if risk_score < 30:
            return {
                'status': 'rejected',
                'reason': 'risk_score_too_low',
                'risk_score': risk_score,
                'message': 'امتیاز ریسک پایین است'
            }
        
        if requested_amount > approved_limit:
            return {
                'status': 'approved',
                'approved_amount': approved_limit,
                'requested_amount': requested_amount,
                'reason': 'amount_adjusted',
                'risk_score': risk_score,
                'message': f'مبلغ درخواستی تعدیل شد. مبلغ تاییدشده: {approved_limit:,} ریال'
            }
        
        return {
            'status': 'approved',
            'approved_amount': requested_amount,
            'requested_amount': requested_amount,
            'risk_score': risk_score,
            'message': 'درخواست تایید شد'
        }
    
    @transaction.atomic
    def _create_credit_limit(self, user, approved_limit: int) -> CreditLimit:
        """Create credit limit record"""
        expiry_date = timezone.localdate() + timedelta(days=CREDIT_LIMIT_DEFAULT_EXPIRY_DAYS)

        credit_limit = CreditLimit.objects.create(
            user=user,
            approved_limit=approved_limit,
            used_limit=0,
            expiry_date=expiry_date,
            status='active',
            approved_at=timezone.now()
        )
        
        return credit_limit
    
    def check_credit_eligibility(self, user, amount: int) -> Dict[str, Any]:
        """Check if user is eligible for requested credit amount"""
        
        credit_limit = CreditLimit.objects.get_user_credit_limit(user)
        
        if not credit_limit:
            return {
                'eligible': False,
                'reason': 'no_active_credit_limit',
                'message': 'حد اعتباری فعال یافت نشد'
            }
        
        if credit_limit.available_limit < amount:
            return {
                'eligible': False,
                'reason': 'insufficient_credit',
                'available_limit': credit_limit.available_limit,
                'requested_amount': amount,
                'message': f'اعتبار کافی نیست. اعتبار موجود: {credit_limit.available_limit:,} ریال'
            }
        
        if credit_limit.status != 'active':
            return {
                'eligible': False,
                'reason': 'credit_limit_inactive',
                'message': 'حد اعتباری غیرفعال است'
            }
        
        return {
            'eligible': True,
            'available_limit': credit_limit.available_limit,
            'message': 'واجد شرایط است'
        }
