# credit/utils/risk_scoring.py

from typing import Dict, Any
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import models


class RiskScoringEngine:
    """Engine for calculating user risk scores"""
    
    def calculate_score(self, user, kyc_data: Dict[str, Any] = None, income_data: Dict[str, Any] = None) -> int:
        """
        Calculate risk score (0-100, higher = lower risk)
        
        Args:
            user: Django user instance
            kyc_data: KYC verification data
            income_data: Income verification data
            
        Returns:
            int: Risk score between 0-100
        """
        score = 50  # Base score
        
        # User profile factors
        if hasattr(user, 'date_joined'):
            account_age = (timezone.now() - user.date_joined).days
            if account_age > 365:
                score += 15
            elif account_age > 180:
                score += 10
            elif account_age > 90:
                score += 5
        
        # KYC verification factors
        if kyc_data:
            if kyc_data.get('national_id_verified'):
                score += 20
            if kyc_data.get('phone_verified'):
                score += 10
            if kyc_data.get('address_verified'):
                score += 10
        
        # Income factors
        if income_data and 'monthly_income' in income_data:
            monthly_income = income_data['monthly_income']
            if monthly_income > 50_000_000:  # > 5M Toman
                score += 15
            elif monthly_income > 30_000_000:  # > 3M Toman
                score += 10
            elif monthly_income > 15_000_000:  # > 1.5M Toman
                score += 5
        
        # Transaction history (if available)
        try:
            from wallets.models import Transaction
            transaction_count = Transaction.objects.filter(
                models.Q(from_wallet__user=user) | models.Q(to_wallet__user=user),
                status='success'
            ).count()
            
            if transaction_count > 50:
                score += 15
            elif transaction_count > 20:
                score += 10
            elif transaction_count > 5:
                score += 5
        except:
            pass
        
        return min(100, max(0, score))
