from rest_framework import serializers
from credit.models.credit_limit import CreditLimit
from credit.models.statement import Statement
from credit.models.statement_line import StatementLine
from django.contrib.auth import get_user_model

User = get_user_model()

class CreditLimitSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    class Meta:
        model = CreditLimit
        fields = [
            'id', 'user', 'approved_limit', 'available_limit', 'used_limit',
            'status', 'expiry_date', 'created_at', 'updated_at', 'reference_code'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'reference_code']

class StatementLineSerializer(serializers.ModelSerializer):
    transaction = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = StatementLine
        fields = [
            'id', 'statement', 'type', 'amount', 'transaction', 'created_at', 'description'
        ]
        read_only_fields = ['id', 'created_at']

class StatementSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    lines = StatementLineSerializer(many=True, read_only=True)
    class Meta:
        model = Statement
        fields = [
            'id', 'user', 'year', 'month', 'reference_code', 'status',
            'opening_balance', 'closing_balance', 'total_debit', 'total_credit',
            'due_date', 'paid_at', 'lines', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'reference_code', 'created_at', 'updated_at', 'lines']
